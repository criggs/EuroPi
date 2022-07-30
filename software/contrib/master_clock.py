from europi import *
import machine
from time import ticks_diff, ticks_ms
from europi_script import EuroPiScript
import uasyncio as asyncio

'''
Master Clock
author: Nik Ansell (github.com/gamecat69)
date: 2022-08-01
labels: clock

This is intended to serve as a master clock and clock divider. Each output sends a trigger of a configurable pulse length.

Demo video: TBC

digital_in: Reset step count on rising edge
analog_in: not used

knob_1: BPM
knob_2: Pulse width

button_1: Start / Stop
button_2: Reset step count when released

output_1: clock / 1
output_2: clock / 2
output_3: clock / 4
output_4: clock / 8
output_5: clock / 16
output_6: clock / 32

'''

class MasterClock(EuroPiScript):
    def __init__(self):
        # Overclock the Pico for improved performance.
        machine.freq(250_000_000)
        self.step = 1
        self.bpm = 100
        self.pulseWidthMs = 10
        self.running = False
        self.MAX_DIVISION = 32
        self.CLOCKS_PER_QUARTER_NOTE = 4
        self.MIN_BPM = 50
        self.MAX_BPM = 200
        self.MIN_PULSE_WIDTH = 8
        self.resetTimeout = 2000
        self.previousStepTime = 0

        self.getSleepTime()
        self.MAX_PULSE_WIDTH = self.timeToSleepMs // 2

        # Get asyncio event loop object
        self.el = asyncio.get_event_loop()
        self.el.run_forever()

        # Starts/Stops the master clock
        @b1.handler_falling
        def StartStop():
            self.running = not self.running

        # Reset step count with button press
        @b2.handler_falling
        def resetButton():
            self.step = 1
        
        # Reset step count upon receiving a din voltage
        @din.handler
        def resetDin():
            self.step = 1

    # Holds given output (cv) high for pulseWidthMs duration
    async def outputPulse(self, cv):
        cv.voltage(5)
        await asyncio.sleep_ms(self.pulseWidthMs)
        cv.off()

    # Given a desired BPM, calculate the time to sleep between clock pulses
    def getSleepTime(self):
        self.timeToSleepMs = int((60000 / self.bpm / self.CLOCKS_PER_QUARTER_NOTE))
    
    def getBPM(self):
        self.bpm = self.MIN_BPM + k1.read_position(steps=(self.MAX_BPM - self.MIN_BPM + 1), samples=512)

    def getPulseWidth(self):
        # Get desired PW percent
        self.pulseWidthPercent = k2.read_position(steps=50, samples=512) + 1
        # Calc Pulse Width duration (x 2 needed because the max is 50%)
        self.pulseWidthMs = int((self.MAX_PULSE_WIDTH * 2) * (self.pulseWidthPercent / 100)) 
        # Don't allow a pulse width less than the minimum
        if self.pulseWidthMs < self.MIN_PULSE_WIDTH:
            self.pulseWidthMs = self.MIN_PULSE_WIDTH
            self.pulseWidthPercent = 'min'

    # Triggered by main. Sends output pulses at required division
    def clockTrigger(self):
        el.create_task(self.outputPulse(cv1))

        if self.step % 2 == 0:
            el.create_task(self.outputPulse(cv2))

        if self.step % 4 == 0:
            el.create_task(self.outputPulse(cv3))

        if self.step % 8 == 0:
            el.create_task(self.outputPulse(cv4))

        if self.step % 16 == 0:
            el.create_task(self.outputPulse(cv5))

        if self.step % 32 == 0:
            el.create_task(self.outputPulse(cv6))

        # advance/reset clock step
        if self.step < self.MAX_DIVISION:
            self.step += 1
        else:
            self.step = 1
        
        # Get time of last step to use in the auto reset function
        self.previousStepTime = time.ticks_ms()

    async def main(self):
        while True:
            self.getBPM()
            self.getSleepTime()
            self.MAX_PULSE_WIDTH = self.timeToSleepMs // 2  # Maximum of 50% pulse width
            self.getPulseWidth()
            self.updateScreen()

            # Auto reset function after resetTimeout
            if self.step != 0 and ticks_diff(ticks_ms(), self.previousStepTime) > self.resetTimeout:
                 self.step = 1

            if self.running:
                self.clockTrigger()
                await asyncio.sleep_ms(self.timeToSleepMs)

    def updateScreen(self):
        # oled.clear() - dont use this, it causes the screen to flicker!
        oled.fill(0)
        oled.text('BPM: ' + str(self.bpm), 0, 1, 1)
        oled.text('PW: ' + str(self.pulseWidthPercent) + '% (' + str(self.pulseWidthMs) + 'ms)', 0, 12, 1)
        oled.text(str(self.step), 112, 0, 1)
        if not self.running:
            oled.text('B1:Start', 0, 23, 1)
        else:
            oled.text('B1:Stop', 0, 23, 1)
        oled.show()

if __name__ == '__main__':
    [cv.off() for cv in cvs]
    mc = MasterClock()
    el = asyncio.get_event_loop()
    el.create_task(mc.main())
    el.run_forever()