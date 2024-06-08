import smbus2
import numpy as np

channel = 1

ADDRESS = int("76", 16) # BME280 I2C address

id_reg = int("D0", 16) # read only should return 0x60
reset_reg = int("E0", 16) # write only
reset_reg_val = int("B6", 16) # reset reg word
config_reg = int("F5", 16) # ctrl reg r/w     standby[7:5] | filter [4:2] | spi3w_en [0] 
status_reg = int("F3", 16) # read only        measuring[3] | im_update[0]
# modes
# 00 - sleep mode
# 01 | 10 - forced mode return to sleep after one measurement 
# 11 - normal mode
ctrl_meas_reg = int("F4", 16) # ctrl reg r/w  osrs_t[7:5]  | osrs_p[4:2]  | mode[1:0]
ctrl_hum_reg = int("F2", 16) # ctrl reg r/w   osrs_h[2:0] - changes saved after calling ctrl_meas_reg!

#calib00..25 data - read only
calib00_reg = 0x88
calib00_width = 26

#calib26-41 data - read only
calib26_reg = 0xE1
calib26_width = 16

# data registers - read only
hum_reg = int("FD", 16)
hum_width = 2
temp_reg = int("FA", 16)
temp_width = 3
pres_reg = int("F7", 16)
pres_width = 3

ctrl_hum_reg_data  = int("00000101", 2) # hum x16 oversampling
ctrl_meas_reg_data = int("10110101", 2) # temp and pres x16 oversampling, forced mode so it consumes less power

bme280 = smbus2.SMBus(channel)

# bme280.write_byte(ADDRESS, read_reg)

id_data = bme280.read_byte_data(ADDRESS, id_reg)
#stat_data1 = bme280.read_byte_data(ADDRESS, status_reg)
# update measurement configuration
bme280.write_byte_data(ADDRESS, ctrl_hum_reg, ctrl_hum_reg_data)
bme280.write_byte_data(ADDRESS, ctrl_meas_reg, ctrl_meas_reg_data)

config_data = bme280.read_byte_data(ADDRESS, config_reg)
stat_data2 = bme280.read_byte_data(ADDRESS, status_reg)
# read upated measurement configuration
ctrl_meas_data = bme280.read_byte_data(ADDRESS, ctrl_meas_reg)
ctrl_hum_data = bme280.read_byte_data(ADDRESS, ctrl_hum_reg)

calibr_data = bme280.read_i2c_block_data(ADDRESS, calib00_reg, calib00_width)
calibr_data.extend(bme280.read_i2c_block_data(ADDRESS, calib26_reg, calib26_width))

# humidity calibration data
hum_calib = bme280.read_i2c_block_data(ADDRESS, 0xA1, 1)
hum_calib.extend(bme280.read_i2c_block_data(ADDRESS, 0xE1, 7))

# temp_data = bme280.read_i2c_block_data(ADDRESS, temp_reg, temp_width)
meas_data = bme280.read_i2c_block_data(ADDRESS, pres_reg, (pres_width+temp_width+hum_width))
pres_data = meas_data[0:pres_width]
temp_data = meas_data[pres_width:pres_width+temp_width]
hum_data  = meas_data[pres_width+temp_width:pres_width+temp_width+hum_width]

# 0x88 - calibr_data[0]
# 0xE7 - calibr_data[41]
calibr_T1 = np.uint16((calibr_data[1] << 8) + calibr_data[0])
calibr_T2 = np.int16 ((calibr_data[3] << 8) + calibr_data[2])
calibr_T3 = np.int16 ((calibr_data[5] << 8) + calibr_data[4])

temp_val = np.int32((temp_data[0] << 12) + (temp_data[1] << 4) + (temp_data[2] >> 4))

temp_var1 = (((temp_val >> 3) - np.int32(calibr_T1<<1)) * (np.int32(calibr_T2))) >> 11
temp_var2 = ((((temp_val >> 4) - (np.int32(calibr_T1))) * ((temp_val >> 4) - np.int32(calibr_T1))) >> 12) * np.int32(calibr_T3) >> 14

t_fine = temp_var1 + temp_var2;
T = (t_fine*5 + 128) >> 8
T /= 100

P_idx = 6
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

H_idx = 25
#H_idx = 0
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

print("---------------------------------")
print(f"id: {hex(id_data)}")
#print(f"status: {bin(stat_data1)}")
print(f"config: {bin(config_data)}")
print(f"ctrl meas: {bin(ctrl_hum_data)} {bin(ctrl_meas_data)}")
print(f"status: {bin(stat_data2)}")

#print(f"calibr data len: {len(calibr_data)}")
#print(f"calibr data: {[hex(calibr) for calibr in calibr_data]}")
#print(f"humidity calibr data: {[hex(calibr_H1), hex(calibr_H2), hex(calibr_H3), hex(calibr_H4), hex(calibr_H5) ,hex(calibr_H6)]}")
#print(f"hum data: {[hex(hum_cal) for hum_cal in hum_calib]}")
print("-----------TEMPERATURE-----------")
print([hex(temp_dat) for temp_dat in temp_data])
print(f"temp_val: {temp_val} hex: {hex(temp_val)}")
print(f"temp: {T} degC")
print("------------PRESSURE-------------")
print([hex(pres_dat) for pres_dat in pres_data])
print(f"pres_val: {pres_val} hex: {hex(pres_val)}")
print(f"pres: {P} hPA") 
print("------------HUMIDITY-------------")
print([hex(hum_dat) for hum_dat in hum_data])
print(f"hum_val: {hum_val} hex: {hex(hum_val)}")
print(f"hum: {H:.2f} %")
print("---------------------------------")

