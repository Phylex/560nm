#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include "pico/binary_info.h"
#include "hardware/irq.h"
#include "hardware/adc.h"
#include "hardware/pwm.h"
#include "hardware/dma.h"

#define BUF_LEN 100
#define MSG_RX 1
#define MSG_TX 2
#define CMD_BYTE 0
#define OPEN_VALVE 1
#define CLOSE_VALVE 2
#define MSG_SIZE 2
#define CAPTURE_DEPTH 2048

const uint LED_PIN = 25;
const uint MOIST_SNS = 26;
const uint I2C_SCL = 1;
const uint I2C_SDA = 0;
const uint VLV_CTRL = 2;
const float conversion_factor = 3.3f / (1 << 12);
const uint I2C_ADDR = 0x30;

// this is the buffer for messages
uint8_t buffer[BUF_LEN];
uint8_t* bp = buffer;
uint8_t message_flag = 0;
uint16_t adc_result = 0;
uint8_t valve_state = 0;

void i2c_handler() {
    // Get interrupt status
    uint32_t status = i2c0->hw->intr_stat;

	// The last transmission was not completed/failed, which is why there are still bytes
	// in the TX-fifo that are automatically flushed. We need to acknowledge this by reading
	// the IC_CLR_TX_ABRT register
	// The peripheral is stateless, so that two consecutive requests will be answered independently
	// from each other, only referencing the device state.
	if (status & I2C_IC_INTR_STAT_R_TX_ABRT_BITS) {
		i2c0->hw->clr_tx_abrt;
	}
	// Check to see if we have received data from the I2C controller
    if (status & I2C_IC_INTR_STAT_R_RX_FULL_BITS) {
		// Read the data (this will clear the interrupt)
		uint8_t rx_fifo_level = (uint8_t)(i2c0->hw->rxflr & I2C_IC_RXFLR_BITS);
		for (uint8_t i = 0; i < rx_fifo_level; i++) {

			// for every entry the data_cmd_reg needs to be read
			uint32_t cmd_reg = i2c0->hw->data_cmd;
			uint8_t value = (uint8_t)(cmd_reg & I2C_IC_DATA_CMD_DAT_BITS);
			// Check if this is the 1st byte we have received
			if (cmd_reg & I2C_IC_DATA_CMD_FIRST_DATA_BYTE_BITS) {
				// as this is a new message, reset the buffer pointer
				bp = buffer;
			}
			if ((bp-buffer) < BUF_LEN) {
				*bp = value;
				bp ++;
			}
		}
		message_flag = MSG_RX;
    }

	// Check to see if the I2C controller is requesting data from the RAM
	if (status & I2C_IC_INTR_STAT_R_RD_REQ_BITS) {

		// Write the data from the current address in RAM
		i2c0->hw->data_cmd = (uint32_t)(adc_result >> 8);
		//i2c0->hw->data_cmd = (uint32_t)(valve_state);

		// Clear the interrupt
		i2c0->hw->clr_rd_req;
	}
}

// i2c0->hw->intr_mask = (I2C_IC_INTR_MASK_M_RD_REQ_BITS | I2C_IC_INTR_MASK_M_RX_FULL_BITS);
void i2c_init_slave_intr(i2c_inst_t* i2c, void (* irq_handler)(void), uint rx_full_thresh, uint32_t interrupts_enabled){
	// this is the threshhold that the rx_full_bits interrupt fires
	// effectively this can set how long a 'request message' needs to be
	// This value can be set to a max of 16 in the case of the rp2040 as then the buffer is full
	i2c->hw->rx_tl = (rx_full_thresh & I2C_IC_RX_TL_RX_TL_BITS);
    // Enable the I2C interrupts we want to process in this case the read-request interrupt
	// and the RX buffer full interrupt (the one we have set to 3 bytes so that it triggers
    i2c->hw->intr_mask = interrupts_enabled;
    // Set up the interrupt handler to service I2C interrupts
	uint irq_num;
	if (i2c == i2c0)
		irq_num = I2C0_IRQ;
	else if (i2c == i2c1)
		irq_num = I2C1_IRQ;
    irq_set_exclusive_handler(irq_num, irq_handler);
    // Enable I2C interrupt
    irq_set_enabled(irq_num, true);
}

uint8_t adc_buf[CAPTURE_DEPTH];
float mean_adc_val;
uint dma_chan;
dma_channel_config dma_cfg;

// adc average function
void adc_dma_average() {
	// reinitialize the dma
	dma_channel_configure(dma_chan, &dma_cfg,
			adc_buf,
			&adc_hw->fifo,
			CAPTURE_DEPTH,
			true
	);
	uint32_t adc_sum = 0;
	for (int i=0; i<CAPTURE_DEPTH; i++) {
		adc_sum += adc_buf[i];
	}
	mean_adc_val = (float)(adc_sum)/CAPTURE_DEPTH;
}

// adc dma buffer allocation and other neccesarily global info

int main() {
	bi_decl(bi_program_description("Firmware for the autonomous plant watering project"));
	bi_decl(bi_1pin_with_name(LED_PIN, "On-board LED"));
	bi_decl(bi_1pin_with_name(MOIST_SNS, "ADC Input from moisture sensor"));
	bi_decl(bi_1pin_with_name(I2C_SDA, "I2C Serial Data Line"));
	bi_decl(bi_1pin_with_name(I2C_SCL, "I2C Serial Clock Line"));
	bi_decl(bi_2pins_with_func(I2C_SCL, I2C_SDA, GPIO_FUNC_I2C));
	bi_decl(bi_1pin_with_name(VLV_CTRL, "Valve control Pin"));

	stdio_init_all();

	// initialize the ADC
	adc_init();
	adc_gpio_init(MOIST_SNS);
	adc_select_input(0);
	adc_fifo_setup(
		true, // write to the sample fifo
		true, // Enable DMA request
		1,    // enable dma request when one sample is present
		false,// no error bit
		true  // shift to eight bits
	);
	// start a new conversion after 4800 cycles
	adc_set_clkdiv(4800);

	// initialize the DMA for the ADC
	dma_chan = dma_claim_unused_channel(true);
	dma_cfg = dma_channel_get_default_config(dma_chan);
	// configure to read from a constant address and write to an incrementing one
	channel_config_set_transfer_data_size(&dma_cfg, DMA_SIZE_8);
	channel_config_set_read_increment(&dma_cfg, false);
	channel_config_set_write_increment(&dma_cfg, true);
	// start transfers on the request of the adc
	channel_config_set_dreq(&dma_cfg, DREQ_ADC);
	dma_channel_configure(dma_chan, &dma_cfg,
			adc_buf,   //dst
			&adc_hw->fifo, //src
			CAPTURE_DEPTH, //size
			true
	);
	dma_channel_set_irq0_enabled(dma_chan, true);
	irq_set_enabled(DMA_IRQ_0, true);
	irq_set_exclusive_handler(DMA_IRQ_0, adc_dma_average);

	// initialize the I2C
	uint baudrate = i2c_init(i2c0, 100000);
	i2c_set_slave_mode(i2c0, true, I2C_ADDR);
	i2c_init_slave_intr(i2c0, i2c_handler, 2, (uint32_t)(I2C_IC_INTR_MASK_M_RD_REQ_BITS | I2C_IC_INTR_MASK_M_RX_FULL_BITS));
	// configure gpio pins for i2c operation
	gpio_set_function(I2C_SCL, GPIO_FUNC_I2C);
	gpio_set_function(I2C_SDA, GPIO_FUNC_I2C);
	// enable the pullups on the i2c line
	gpio_pull_up(I2C_SDA);
	gpio_pull_up(I2C_SCL);

	// initialize the valve output
	gpio_init(VLV_CTRL);
	gpio_set_dir(VLV_CTRL, GPIO_OUT);

	while (true) {
		if (message_flag == MSG_RX) {
			printf("Received i2c packet\n");
			uint8_t size = bp - buffer;
			if (size != MSG_SIZE){
				printf("Invalid size of %d", size);
				bp = buffer;
				continue;
			}
			switch (buffer[CMD_BYTE]) {
				case OPEN_VALVE:
					gpio_put(VLV_CTRL, 1);
					break;
				case CLOSE_VALVE:
					gpio_put(VLV_CTRL, 0);
					break;
			}
			printf("Message Contents: ");
			for (uint8_t i=0; i<(bp-buffer); i++) {
				printf("0x%02x ", buffer[i]);
			}
			printf("\n");
			message_flag = 0;
		}
	}
}
