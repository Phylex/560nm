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
#define MOIST_CHAN 0
#define LIGHT_CHAN 1

const uint LED_PIN = 25;
const uint MOIST_SNS = 26;
const uint LIGHT_SNS = 27;
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

uint8_t adc_buf[CAPTURE_DEPTH];
uint adc_chan = 0;
float moisture = 0;
float lightness = 0;
uint dma_chan;
dma_channel_config dma_cfg;

void i2c_handler() {
	printf("i2c handler\n");
    // Get interrupt status
    uint32_t status = i2c0->hw->intr_stat;

	// The last transmission was not completed/failed, which is why there are still bytes
	// in the TX-fifo that are automatically flushed. We need to acknowledge this by reading
	// the IC_CLR_TX_ABRT register
	// The peripheral is stateless, so that two consecutive requests will be answered independently
	// from each other, only referencing the device state.
	if (status & I2C_IC_INTR_STAT_R_TX_ABRT_BITS) {
		printf("tx abbort\n");
		uint32_t abrt_reg = i2c0->hw->clr_tx_abrt;
	}
	// Check to see if we have received data from the I2C controller
    if (status & I2C_IC_INTR_STAT_R_RX_FULL_BITS) {
		// Read the data (this will clear the interrupt)
		uint8_t rx_fifo_level = (uint8_t)(i2c0->hw->rxflr & I2C_IC_RXFLR_BITS);
		printf("receivied a i2c packet\n");
		for (uint8_t i = 0; i < rx_fifo_level; i++) {

			// for every entry the data_cmd_reg needs to be read
			uint32_t cmd_reg = i2c0->hw->data_cmd;
			uint8_t value = (uint8_t)(cmd_reg & I2C_IC_DATA_CMD_DAT_BITS);
			printf("byte %d: 0x%02x\n", i, value);
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
		printf("read request\n");
		// Clear the interrupt
		i2c0->hw->clr_rd_req;
		// Write the data from the current address in RAM
		if ((i2c0->hw->rxflr & I2C_IC_RXFLR_BITS) == 0) {
			printf("writing bytes in read request\n");
			uint8_t byte_array[4];
			*((float *)byte_array) = moisture;
			for (int i=0; i<sizeof(float); i++) {
				i2c0->hw->data_cmd = (uint32_t)(byte_array[i]);
			}
			*((float *)byte_array) = lightness;
			for (int i=0; i<sizeof(float); i++) {
				i2c0->hw->data_cmd = (uint32_t)(byte_array[i]);
			}
		}
		message_flag = MSG_TX;
	}
	printf("exiting i2c handler\n");
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

void adc_handler() {
	printf("adc_handler\n");
	adc_run(false);
	adc_fifo_drain();
	dma_hw->ints0 = (1u << dma_chan);
	uint32_t adc_sum = 0;
	for (int i=0; i<CAPTURE_DEPTH; i++) {
		adc_sum += adc_buf[i];
	}
	float adc_mean = (float)(adc_sum)/CAPTURE_DEPTH;
	if (adc_chan == MOIST_CHAN){
		moisture = adc_mean;
		adc_chan = LIGHT_CHAN;
		adc_select_input(adc_chan);
	} else if (adc_chan == LIGHT_CHAN){
		lightness = adc_mean;
		adc_chan = MOIST_CHAN;
		adc_select_input(adc_chan);
	}
	dma_channel_set_write_addr(dma_chan, adc_buf, true);
	adc_run(true);
}

int main() {
	// name the pins;
	bi_decl(bi_program_description("Firmware for the autonomous plant watering project"));
	bi_decl(bi_1pin_with_name(LED_PIN, "On-board LED"));
	bi_decl(bi_1pin_with_name(MOIST_SNS, "ADC Input from moisture sensor"));
	bi_decl(bi_1pin_with_name(I2C_SDA, "I2C Serial Data Line"));
	bi_decl(bi_1pin_with_name(I2C_SCL, "I2C Serial Clock Line"));
	bi_decl(bi_2pins_with_func(I2C_SCL, I2C_SDA, GPIO_FUNC_I2C));
	bi_decl(bi_1pin_with_name(VLV_CTRL, "Valve control Pin"));
	bi_decl(bi_1pin_with_name(LIGHT_SNS, "ADC Input of the photo-resistor" ));
	// initialize the stdio
	stdio_init_all();
	sleep_ms(2000);
	// initialize the ADC
	printf("setting up adc\n");
	adc_init();
	adc_gpio_init(MOIST_SNS);
	adc_gpio_init(LIGHT_SNS);
	adc_fifo_setup(
		true, // write to the sample fifo
		true, // Enable DMA request
		1,    // enable dma request when one sample is present
		false,// no error bit
		true  // shift to eight bits
	);
	// set the adc
	adc_set_clkdiv(24000);

	// initialize the DMA for the ADC
	printf("setting up dma\n");
	dma_chan = dma_claim_unused_channel(false);
	if (dma_chan == -1) {
		printf("dma channel could not be aquired\n");
	}
	dma_cfg = dma_channel_get_default_config(dma_chan);
	// configure to read from a constant address and write to an incrementing one
	channel_config_set_transfer_data_size(&dma_cfg, DMA_SIZE_8);
	channel_config_set_read_increment(&dma_cfg, false);
	channel_config_set_write_increment(&dma_cfg, true);
	// start transfers on the request of the adc
	channel_config_set_dreq(&dma_cfg, DREQ_ADC);
	// initialize the interrupt
	dma_channel_set_irq0_enabled(dma_chan, true);
	irq_set_exclusive_handler(DMA_IRQ_0, adc_handler);
    irq_set_enabled(DMA_IRQ_0, true);
	// configure the channel and start up the dma
	adc_chan = MOIST_CHAN;
	adc_select_input(adc_chan);
	dma_channel_configure(dma_chan, &dma_cfg,
			adc_buf,   //dst
			&adc_hw->fifo, //src
			CAPTURE_DEPTH, //size
			true //start now
	);
	
	printf("setting up i2c\n");
	// initialize the I2C
	uint baudrate = i2c_init(i2c0, 100000);
	i2c_set_slave_mode(i2c0, true, I2C_ADDR);
	i2c_init_slave_intr(i2c0, i2c_handler, 2, (uint32_t)(I2C_IC_INTR_MASK_M_RD_REQ_BITS | 
	                                                     I2C_IC_INTR_MASK_M_RX_FULL_BITS | 
	                                                     I2C_IC_INTR_MASK_M_TX_ABRT_BITS));
	// configure gpio pins for i2c operation
	gpio_set_function(I2C_SCL, GPIO_FUNC_I2C);
	gpio_set_function(I2C_SDA, GPIO_FUNC_I2C);
	// enable the pullups on the i2c line
	gpio_pull_up(I2C_SDA);
	gpio_pull_up(I2C_SCL);

	// initialize the valve output
	gpio_init(VLV_CTRL);
	gpio_set_dir(VLV_CTRL, GPIO_OUT);

	// set the adc running and start the moisture and brightness sensing
	printf("starting adc\n");
	adc_run(true);


	while (true) {
		if (message_flag == MSG_RX) {
			printf("Received i2c packet\n");
			uint8_t size = (bp - buffer);
			if (size != MSG_SIZE + 1){
				printf("Invalid size of %d", size);
				bp = buffer;
				message_flag = 0;
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
		} else if (message_flag == MSG_TX) {
			printf("sent moist val of %f\nand light val of %f\n",
			       moisture,
			       lightness);
			message_flag = 0;
		}
	}
}
