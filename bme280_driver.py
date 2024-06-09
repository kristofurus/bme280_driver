import smbus2
import time
import datetime
import sqlite3
import numpy as np

# I2C channel and slave address
channel = 1
ADDRESS = 0x76 # BME280 I2C address

# sleep time
SLEEP_TIME = 5*60 # 5 minutes

# -------------------------------------------------------------------------------
# Register addresses
# -------------------------------------------------------------------------------
ID_REG          = 0xD0 # read only should return 0x60
RESET_REG       = 0xE0 # write only
RESET_REG_VAL   = 0xB6 # reset reg word
CONFIG_REG      = 0xF5 # ctrl reg r/w     standby[7:5] | filter [4:2] | spi3w_en [0] 
STATUS_REG      = 0xF3 # read only        measuring[3] | im_update[0]
# modes
# 00 - sleep mode
# 01 | 10 - forced mode return to sleep after one measurement 
# 11 - normal mode
CTRL_MEAS_REG   = 0xF4 # ctrl reg r/w  osrs_t[7:5]  | osrs_p[4:2]  | mode[1:0]
CTRL_HUM_REG    = 0xF2 # ctrl reg r/w   osrs_h[2:0] - changes saved after calling ctrl_meas_reg!

#calib00..25 data - read only
CALIB00_REG     = 0x88
CALIB00_WIDTH   = 26

#calib26-41 data - read only
CALIB26_REG     = 0xE1
CALIB26_WIDTH   = 16

# data registers - read only
HUM_REG         = 0xFD
HUM_WIDTH       = 2
TEMP_REG        = 0xFA
TEMP_WIDTH      = 3
PRES_REG        = 0xF7
PRES_WIDTH      = 3

CTRL_HUM_REG_DATA  = 0b00000101 # hum x16 oversampling
CTRL_MEAS_REG_DATA = 0b10110101 # temp and pres x16 oversampling, forced mode so it consumes less power

# -------------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------------

def bme280_get_id(bme280):
        id_data = bme280.read_byte_data(ADDRESS, ID_REG)
        return id_data


def bme280_get_config(bme280):
    config_data = bme280.read_byte_data(ADDRESS, CONFIG_REG)
    return config_data


def bme280_status(bme280):
    stat_data = bme280.read_byte_data(ADDRESS, STATUS_REG)
    return stat_data

    
def bme280_set_ctrl_data(bme280, ctrl_hum, ctrl_meas):
    bme280.write_byte_data(ADDRESS, CTRL_HUM_REG, ctrl_hum)
    bme280.write_byte_data(ADDRESS, CTRL_MEAS_REG, ctrl_meas)


def bme280_get_ctrl_data(bme280):
    ctrl_meas_data = bme280.read_byte_data(ADDRESS, CTRL_MEAS_REG)
    ctrl_hum_data = bme280.read_byte_data(ADDRESS, CTRL_HUM_REG)

    return(ctrl_hum_data, ctrl_meas_data)


def bme280_calibrate(bme280):
    calibr_data = bme280.read_i2c_block_data(ADDRESS, CALIB00_REG, CALIB00_WIDTH)
    calibr_data.extend(bme280.read_i2c_block_data(ADDRESS, CALIB26_REG, CALIB26_WIDTH))
    return calibr_data


def bme280_measure(bme280):
    # change mode to to forced mode for single measurement
    bme280.write_byte_data(ADDRESS, CTRL_MEAS_REG, CTRL_MEAS_REG_DATA)
    # temp_data = bme280.read_i2c_block_data(ADDRESS, temp_reg, temp_width)
    meas_data = bme280.read_i2c_block_data(ADDRESS, PRES_REG, (PRES_WIDTH+TEMP_WIDTH+HUM_WIDTH))
    return meas_data


def bme280_get_t_fine(temp_data, calibr_data):
    calibr_T1 = np.uint16((calibr_data[1] << 8) + calibr_data[0])
    calibr_T2 = np.int16 ((calibr_data[3] << 8) + calibr_data[2])
    calibr_T3 = np.int16 ((calibr_data[5] << 8) + calibr_data[4])

    temp_val = np.int32((temp_data[0] << 12) + (temp_data[1] << 4) + (temp_data[2] >> 4))

    temp_var1 = (((temp_val >> 3) - np.int32(calibr_T1<<1)) * (np.int32(calibr_T2))) >> 11
    temp_var2 = ((((temp_val >> 4) - (np.int32(calibr_T1))) * ((temp_val >> 4) - np.int32(calibr_T1))) >> 12) * np.int32(calibr_T3) >> 14

    t_fine = temp_var1 + temp_var2
    return t_fine


def bme280_calcT(t_fine):
    T = (t_fine*5 + 128) >> 8
    T /= 100
    return T

def bme280_calcP(pres_data, calibr_data, P_idx, t_fine):
    calibr_P1 = np.uint16((calibr_data[P_idx+ 1] << 8) + calibr_data[P_idx   ])
    calibr_P2 = np.int16 ((calibr_data[P_idx+ 3] << 8) + calibr_data[P_idx+ 2])
    calibr_P3 = np.int16 ((calibr_data[P_idx+ 5] << 8) + calibr_data[P_idx+ 4])
    calibr_P4 = np.int16 ((calibr_data[P_idx+ 7] << 8) + calibr_data[P_idx+ 6])
    calibr_P5 = np.int16 ((calibr_data[P_idx+ 9] << 8) + calibr_data[P_idx+ 8])
    calibr_P6 = np.int16 ((calibr_data[P_idx+11] << 8) + calibr_data[P_idx+10])
    calibr_P7 = np.int16 ((calibr_data[P_idx+13] << 8) + calibr_data[P_idx+12])
    calibr_P8 = np.int16 ((calibr_data[P_idx+15] << 8) + calibr_data[P_idx+14])
    calibr_P9 = np.int16 ((calibr_data[P_idx+17] << 8) + calibr_data[P_idx+16])

    pres_val = np.uint32((pres_data[0] << 12) + (pres_data[1] << 4) + (pres_data[2] >> 4))

    pres_var1 = np.int64(t_fine) - 128000
    pres_var2 = pres_var1 * pres_var1 * np.int64(calibr_P6)
    pres_var2 += ((pres_var1 * np.int64(calibr_P5)) << 17)
    pres_var2 += (np.int64(calibr_P4) << 35)
    pres_var1 = ((pres_var1 * pres_var1 * np.int64(calibr_P3)) >> 8) + ((pres_var1 * np.int64(calibr_P2)) << 12)
    pres_var1 = ((np.int64(1) << 47) + pres_var1) * np.int64(calibr_P1) >> 33
    if pres_var1 == 0:
        P = np.int64(0)
    else:
        P = np.int64(1048576 - pres_val)
        P = np.int64((((P << 31) - pres_var2)*3125) / pres_var1)
        pres_var1 = np.int64(calibr_P9) * (P >> 13) * (P >> 13) >> 25
        pres_var2 = (np.int64(calibr_P8) * P) >> 19
        P = ((P + pres_var1 + pres_var2) >> 8) + (np.int64(calibr_P7)<< 4)
        P = np.uint32(P)
    P /= 256
    P /= 100
    return P

def bme280_calcH(hum_data, calibr_data, H_idx, t_fine):
    calibr_H1 = np.uint8( calibr_data[H_idx  ])
    calibr_H2 = np.int16((calibr_data[H_idx+2] << 8) +   calibr_data[H_idx+1])
    calibr_H3 = np.uint8( calibr_data[H_idx+3])
    calibr_H4 = np.int16((calibr_data[H_idx+4] << 4) +  (calibr_data[H_idx+5]       & 0x0F))
    calibr_H5 = np.int16((calibr_data[H_idx+6] << 4) + ((calibr_data[H_idx+5] >> 4) & 0x0F))
    calibr_H6 = np.int8 ( calibr_data[H_idx+7])

    hum_val = np.int32((hum_data[0] << 8) + hum_data[1])

    H = t_fine - np.int32(76800)
    H = ((((hum_val << 14) - ((np.int32(calibr_H4)) << 20) - ((np.int32(calibr_H5)) * H)) + (np.int32(16384))) >> 15) \
            * (((((((H * (np.int32(calibr_H6)) >> 10) * (((H * (np.int32(calibr_H3))) >> 11) \
            + (np.int32(32768)))) >> 10) + (np.int32(2097152))) * (np.int32(calibr_H2)) + 8192) >> 14))
    H = H - (((((H >> 15) * (H >> 15)) >> 7) * (np.int32(calibr_H1))) >> 4)
    print(H)
    H = 0 if H < 0 else H     
    H = 419430400 if H > 419430400 else H
    H = H >> 12
    H = np.uint32(H)
    H = H / 1024
    return H


def log_config(id_data, config_data, ctrl_hum_data, ctrl_meas_data, stat_data):
    print("----------CONFIGURATION----------")
    print(f"id: {hex(id_data)}")
    print(f"config: {bin(config_data)}")
    print(f"ctrl meas: {bin(ctrl_hum_data)} {bin(ctrl_meas_data)}")
    print(f"status: {bin(stat_data)}")
    print("---------------------------------")


def log_temp(temp_data, T):
    print("-----------TEMPERATURE-----------")
    print([hex(temp_dat) for temp_dat in temp_data])
    # print(f"temp_val: {temp_val} hex: {hex(temp_val)}")
    print(f"temp: {T} degC")


def log_pres(pres_data, P):
    print("------------PRESSURE-------------")
    print([hex(pres_dat) for pres_dat in pres_data])
    # print(f"pres_val: {pres_val} hex: {hex(pres_val)}")
    print(f"pres: {P} hPA")


def log_hum(hum_data, H):
    print("------------HUMIDITY-------------")
    print([hex(hum_dat) for hum_dat in hum_data])
    # print(f"hum_val: {hum_val} hex: {hex(hum_val)}")
    print(f"hum: {H:.2f} %")


def log_time():
    print("-------------TIME----------------")
    print(datetime.datetime.now())


def save_to_db(T, H, P):
    con = sqlite3.connect("instance/bme280.db")
    cur = con.cursor()
    data = [datetime.datetime.now(), T, H, P]
    cur.execute("INSERT INTO bme280(receive_time, temp, hum, pres) VALUES(?, ?, ?, ?)", data)
    con.commit()
    con.close()


if __name__ == "__main__":
    # connect bme280 to I2C-1 on raspberry pi
    bme280 = smbus2.SMBus(channel)

    bme280_id = bme280_get_id(bme280)
    bme280_config = bme280_get_config(bme280)
    bme280_set_ctrl_data(bme280, CTRL_HUM_REG_DATA, CTRL_MEAS_REG_DATA)
    bme280_ctrl = bme280_get_ctrl_data(bme280)
    bme280_stat = bme280_status(bme280)
    log_config(bme280_id, bme280_config, bme280_ctrl[0], bme280_ctrl[1], bme280_stat)

    calibr_data = bme280_calibrate(bme280)

    while(True):
        meas_data = bme280_measure(bme280)
        pres_data = meas_data[0:PRES_WIDTH]
        temp_data = meas_data[PRES_WIDTH:PRES_WIDTH+TEMP_WIDTH]
        hum_data  = meas_data[PRES_WIDTH+TEMP_WIDTH:PRES_WIDTH+TEMP_WIDTH+HUM_WIDTH]
        P_idx = 6
        H_idx = 25

        t_fine = bme280_get_t_fine(temp_data, calibr_data)
        T = bme280_calcT(t_fine)
        P = bme280_calcP(pres_data, calibr_data, P_idx, t_fine)
        H = bme280_calcH(hum_data, calibr_data, H_idx, t_fine)

        log_time()
        log_temp(temp_data, T)
        log_pres(pres_data, P)
        log_hum(hum_data, H)

        save_to_db(T, H, P)

        time.sleep(SLEEP_TIME)
    