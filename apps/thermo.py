from m5stack import *
from m5ui import *
from machine import Pin, I2C
import time
import struct
import math
import wifiCfg
import urequests

WIFI_SSID = ""
WIFI_PASS = ""
SLACK_APP_URL = ""

def stdev(v):
  u = sum(v) / len(v)
  total = 0.0
  for x in v:
    total += math.pow(x-u, 2.0)
  return math.sqrt(total/len(v))

def adjust(raw, se):
  return 1.68 * raw - 5.37 * se - 0.3

class TemperatureConverter():

  def __init__(self, min, max):
    self.min = min
    self.max = max

  def enhance(self,x):
    if x <= -1.0:
      return 0
    if x >= 1.0:
      return 0
    if x < 0:
      return x+1.0
    return -1.0*(x-1.0)

  def to_color(self,t):
    d = (t-self.min)/(self.max-self.min)*2.0-1.0
    r = 0xFF * self.enhance(d-1.0)
    g = 0xFF * self.enhance(d)
    b = 0xFF * self.enhance(d+1.0)
    rgb = (int(r)<<16) + (int(g)<<8) + int(b)
    return rgb

class ResultWindow():
  def __init__(self, left, top, tc):
    self.left = left
    self.top = top
    self.tc = tc

  def display(self):
    txt0 = "{:.1f}".format(self.temperature)
    lcd.font(lcd.FONT_7seg, width=3)
    lcd.textClear(self.left, self.top, txt0, color=0xA5A5A5)
    lcd.text(self.left, self.top, txt0, color=self.tc.to_color(self.temperature))

  def set_temperature(self, value):
    self.temperature = value


class InfoWindow():
  def __init__(self, left, top, tc):
    self.left = left
    self.top = top
    self.tc = tc

  def display(self):
    txt1 = "{:4.1f}".format(self.raw)
    txt2 = "{:4.1f}".format(self.stdev)
    txt3 = "{:4.1f}".format(self.thermistor)
    lcd.font(lcd.FONT_Small)
    lcd.textClear(self.left + 2, self.top + 7, txt1, color=0xFBFBFB)
    lcd.text(self.left + 2, self.top + 7, txt1)
    lcd.textClear(self.left + 2, self.top + 24, txt2, color=0xFBFBFB)
    lcd.text(self.left + 2, self.top + 24, txt2)
    lcd.textClear(self.left + 2, self.top + 42, txt3, color=0xFBFBFB)
    lcd.text(self.left + 2, self.top + 42, txt3)
    pass

  def set_thermistor(self, value):
    self.thermistor = value

  def set_stdev(self, value):
    self.stdev = value

  def set_raw(self, value):
    self.raw = value

class ResultSet:
  def __init__(self):
    self.data = []
  
  def add(self,value):
    self.data.append(value)

  def average(self):
    return sum(self.data) / len(self.data)

def display_temperature(temp, left, top, size, tc, invert=True):
  for i in range(64):
    c = tc.to_color(temp[i])
    x = (i%8)*size
    if invert:
      x = size*7-x
    x += left
    y = int(i/8)*size+top
    lcd.rect(x,y,size,size,fillcolor=c, color=c)

def do():
  AMG88_ADDR = 0x69

  lcd.image(0,0, "apps/thermo/bg.jpg", 0, lcd.JPG)
  lcd.font(lcd.FONT_Ubuntu)
  lcd.setTextColor(color=0x404040, bcolor=0xDDDDDD)
  title0 = M5Title(title="Thermo ver.01", x=5 , fgcolor=0xFFFFFF, bgcolor=0x0080E0)

  resultSet = ResultSet()

  # setup hardware
  # SDA
  pin21 = Pin(21, Pin.IN, pull=Pin.PULL_UP)
  # SCL
  pin22 = Pin(22, Pin.IN, pull=Pin.PULL_UP)
  i2c = I2C(sda=21, scl=22, freq=400000)

  # result-set of a frame
  temp = 64 * [0.0]

  tc = TemperatureConverter(min=20.0, max=40.0)
  info = InfoWindow(left=100, top=120, tc=tc)
  result = ResultWindow(left=11, top=31, tc=tc)

  for loop in range(30):
    # measure
    data_t = i2c.readfrom_mem(AMG88_ADDR, 0x80, 128)
    data_tth = i2c.readfrom_mem(AMG88_ADDR, 0x0E, 2)
    
    # decode
    # ignoring negative values
    for i in range(64):
      t = int.from_bytes(data_t[i*2:i*2+2], 'little', True) * 0.25
      temp[i] = t

    # thermistor
    tth = int.from_bytes(data_tth, 'little', True) * 0.0625

    # display as graphics
    SIZE = 20
    LEFT = 153
    TOP = 35
    display_temperature(temp, LEFT, TOP, SIZE, tc, invert=True)

    # use top N in matrix
    temp.sort(reverse=True)

    info.set_thermistor(tth)

    VALID = 6
    average_t = sum(temp[0:VALID]) / VALID
    info.set_raw(average_t)

    se = stdev(temp)
    info.set_stdev(se)

    v = adjust(average_t, se)
    resultSet.add(v)
    result.set_temperature(resultSet.average())

    result.display()
    info.display()

    # wait
    time.sleep_ms(50)
  
  return resultSet.average()

global theResult

# MEASURE
def buttonB_wasPressed():
  global theResult
  theResult = do()
btnB.wasPressed(buttonB_wasPressed)

#main
theResult = do()

# QR
def buttonA_wasPressed():
  global theResult
  lcd.qrcode("{:.1f}".format(theResult), 146, 28, 172)
  pass
btnA.wasPressed(buttonA_wasPressed)

# SEND
def buttonC_wasPressed():
  global theResult

  msg = "{:15s}".format("connecting...")
  lcd.textClear(160, 0, msg, 0x0080E0)
  lcd.text(160, 0, msg, 0xFFFFFF)

  if not wifiCfg.wlan_sta.isconnected():
    wifiCfg.doConnect(WIFI_SSID, WIFI_PASS)

  msg = "{:15s}".format("connected")
  lcd.textClear(160, 0, msg, 0x0080E0)
  lcd.text(160, 0, msg, 0xFFFFFF)

  data = { "text" : "{:.1f}".format(theResult) }
  res = urequests.post(SLACK_APP_URL, json=data)

  msg = "{:15s}".format("completed")
  lcd.textClear(160, 0, msg, 0x0080E0)
  lcd.text(160, 0, msg, 0xFFFFFF)

btnC.wasPressed(buttonC_wasPressed)
