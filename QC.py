import pandas as pd
import numpy as np
from datetime import datetime
#library to check if it's land or not
from global_land_mask import globe
#library to calculate the speed
import geopy.distance


class QC(object):
    def __init__(self, df, vessel, gear_type, zone, sensor_type):
        self.vessel = vessel
        self.gear = gear_type
        self.zone = zone
        self.sensor_type = sensor_type
        self.d_regions = {'Flid': 'North Sea', 'LofotonAA': 'Atlantic', 'Pedro': 'North Sea'}
        self.df = df
        self.df['DATETIME'] = pd.to_datetime(self.df['DATETIME'])
        self.df['flag'] = 1
        self.regions()
        self.gear_type()
        self.impossible_date()
        self.impossible_location()
        self.position_on_land()
        self.impossible_speed()
        self.global_range()
        self.spike()
        self.rollover()
        self.stuck()
        self.rate_of_change()
        self.timing_gap()
        self.climatology()
        self.drift()

    # 1. Platform identification, from line 93 load_cloud.py

    # 2. Vessel ID control
    # d represent a dictionary where the keys are the vessels and the values represent the pertinent region
    def regions(self):
        self.df['flag_vessel_region'] = 1
        region = 'Unknown'
        max_lat = self.df['LATITUDE'].max()
        min_lat = self.df['LATITUDE'].min()
        max_lon = self.df['LONGITUDE'].max()
        min_lon = self.df['LONGITUDE'].min()

        if -60 <= max_lon <= -15 and 55 <= max_lat <= 90 and -60 <= min_lon <= -15 and 55 <= min_lat <= 90:
            region = 'Greenland'
        elif -15 <= max_lon <= 30 and 45 <= max_lat <= 60 and -15 <= min_lon <= 30 and 45 <= min_lat:
            region = 'North Sea'
        elif -75 <= max_lon <= 30 and 55 <= max_lat <= 90 and -75 <= min_lon <= 30 and 55 <= min_lat <= 90:
            region = 'Atlantic'
        elif (160 <= max_lon <= 180 or 0 <= max_lon <= 5) and -50 <= max_lat <= -30 and (
                160 <= min_lon <= 180 or 0 <= min_lon <= 5) and -50 <= min_lat <= -30:
            region = 'New Zeland'
        elif -180 <= max_lon <= -125 and 45 <= max_lat <= 90 and -180 <= min_lon <= -125 and 45 <= min_lat <= 90:
            region = 'Alaska'

        if self.d_regions[self.vessel] != region:
            self.df['flag_vessel_region'] = 3
            self.df['flag'] = 3

    # 3. Gear type control
    # Still some thoughts need to be applied
    def gear_type(self):
        # gt = 0 = fixed
        # gt = 1 = mobile
        self.df['flag_gear_type'] = 1
        if len(self.df) != 0:
            coords_1 = self.df.LATITUDE.iloc[0], self.df.LONGITUDE.iloc[0]
            coords_2 = self.df.LATITUDE.iloc[-1], self.df.LONGITUDE.iloc[-1]
            d = geopy.distance.geodesic(coords_1, coords_2).m
            print('Distance between profiles ', d)
        else:
            return

        gt = 1 if d > 200 else 0

        if (gt == 1 and self.gear == 'Fixed') or (gt == 0 and self.gear == 'Mobile'):
            self.df['flag_gear_type'] = 3
            self.df['flag'] = 3

    # 4. Impossible date test
    # The date of the profile can be no earlier than 01/01/2010 and no later than current date in UTC

    def impossible_date(self):
        self.df['flag_date'] = 1
        currdate = datetime.utcnow()
        mindate = datetime(2010, 1, 1)
        self.df.loc[((self.df['DATETIME'] > currdate) | (self.df['DATETIME'] < mindate)), ['flag_date', 'flag']] = 4

    # 5. Impossible location test
    # Requires the observation latitude and longitude to be sensible

    def impossible_location(self):
        self.df['flag_location'] = 1
        latrange = [-90, 90]
        lonrange = [-180, 180]
        self.df.loc[((self.df['LATITUDE'] < latrange[0]) | (self.df['LATITUDE'] > latrange[1]) | (
                    self.df['LONGITUDE'] < lonrange[0]) | (self.df['LONGITUDE'] > lonrange[1])), ['flag_location',
                                                                                                  'flag']] = 4

    # 6. Position on land test
    # Tests if the observation longitude and latitude from a profile is located in an ocean, based on ETOPO5.

    def position_on_land(self):
        self.df['flag_land'] = 1
        self.df.loc[(globe.is_land(self.df['LATITUDE'], self.df['LONGITUDE'])), ['flag_land', 'flag']] = 4

    # 7. Impossible speed test
    # Drift speeds calculated given the positions and times of the floats, can't exceed 3m/s

    def impossible_speed(self):
        self.df['flag_speed'] = 1
        self.df['speed'] = 0
        self.df.reset_index(drop=True, inplace=True)
        if len(self.df) != 0:
            for i in self.df.iloc[:-1].index:
                time1 = self.df.DATETIME.iloc[i]
                time2 = self.df.DATETIME.iloc[i + 1]
                coords_1 = self.df.LATITUDE.iloc[i], self.df.LONGITUDE.iloc[i]
                coords_2 = self.df.LATITUDE.iloc[i + 1], self.df.LONGITUDE.iloc[i + 1]
                d = geopy.distance.geodesic(coords_1, coords_2).m
                t = (time2 - time1).seconds
                self.df['speed'].iloc[i] = d / t if t != 0 else None
            if self.df['speed'].mean() != 0:
                self.df['flag_speed'] = 1
                self.df.loc[(self.df['speed'] > 4.12), ['flag_speed', 'flag']] = 4
            # self.df = self.df[self.df['flag_speed'] == 1]
            self.df = self.df.drop(columns=['speed'])

    # 8. Global range test
    # Gross filter on the observed values of pressure, temperature and salinity
    def global_range(self):
        max_press, min_temp, max_temp, min_sal, max_sal = None, None, None, None, None
        if self.sensor_type == 'NKE':
            min_temp, max_temp = -2, 35
            max_press = 1000 * 1.1
            if 'SALINITY' in self.df:
                min_sal, max_sal = 2, 42
                max_press = 300 * 1.1
        elif self.sensor_type == 'ZebraTech':
            min_temp, max_temp = -2, 35
            max_press = 1000 * 1.1
        elif self.sensor_type == 'Lowell':
            min_temp, max_temp = -5, 50
            max_press = 1000 * 1.5
        elif self.sensor_type == 'Marport':
            min_temp, max_temp = -5, 25
            max_press = 600 * 1.1
        elif self.sensor_type == 'Hobo':
            min_temp, max_temp = -20, 50
            max_press = 600 * 1.5

        self.df['flag_global_range'] = 1
        self.df.loc[(self.df['PRESSURE'] >= -5) & (self.df['PRESSURE'] < 0), ['flag_global_range', 'flag']] = 3
        self.df.loc[self.df['PRESSURE'] > max_press, ['flag_global_range', 'flag']] = 3
        self.df.loc[(self.df['PRESSURE'] < -5), ['flag_global_range', 'flag']] = 4
        self.df.loc[((self.df['TEMPERATURE'] < min_temp) | (self.df['TEMPERATURE'] > max_temp)), ['flag_global_range', 'flag']] = 4
        if 'SALINITY' in self.df:
            self.df.loc[((self.df['SALINITY'] < min_sal) | (self.df['SALINITY'] > max_sal)), ['flag_global_range', 'flag']] = 4

    # 9. Spike test
    def spike(self):
        ## Temperature
        self.df['flag_temp_spike'] = 1
        self.df['prev_temp'] = self.df['TEMPERATURE'].shift(1)
        self.df['post_temp'] = self.df['TEMPERATURE'].shift(-1)
        self.df['val'] = abs(self.df.TEMPERATURE - (self.df.post_temp + self.df.prev_temp) / 2) - abs(
            (self.df.post_temp - self.df.prev_temp) / 2)
        self.df.loc[(((self.df['PRESSURE'] < 500) & (self.df['val'] > 6)) | (
                    (self.df['PRESSURE'] >= 500) & (self.df['val'] > 2))), ['flag_temp_spike', 'flag']] = 4
        self.df = self.df.drop(columns=['prev_temp', 'post_temp', 'val'])

        ## Salinity
        if 'SALINITY' in self.df:
            self.df['flag_sal_spike'] = 1
            self.df['prev_sal'] = self.df['SALINITY'].shift(1)
            self.df['post_sal'] = self.df['SALINITY'].shift(-1)
            self.df['val'] = abs(self.df.SALINITY - (self.df.post_sal + self.df.prev_sal) / 2) - abs(
                (self.df.post_sal - self.df.prev_sal) / 2)
            self.df.loc[(((self.df['PRESSURE'] < 500) & (self.df['val'] > 0.9)) | (
                    (self.df['PRESSURE'] >= 500) & (self.df['val'] > 0.3))), ['flag_sal_spike', 'flag']] = 4
            self.df = self.df.drop(columns=['prev_sal', 'post_sal', 'val'])

    # 10. Digit rollover test adapted to:
    # Bottom Spike test
    # This is a special version of the spike test, which
    # compares the measurements at the end of the
    # profile to the adjacent measurement. Temperature
    # at the bottom should not differ from the adjacent
    # measurement by more than 1°C
    def rollover(self):
        ## Temperature
        self.parse_segments()
        self.df['flag_rollover'] = 1
        self.df['prev_temp'] = self.df['TEMPERATURE'].shift(1)
        self.df.loc[
            (abs(self.df['TEMPERATURE'] - self.df['prev_temp']) > 0.5) & (self.df['type'] == 3), ['flag_rollover',
                                                                                                  'flag']] = 3
        self.df = self.df.drop(columns=['prev_temp'])

    #         ## Salinity
    #         if 'SALINITY' in self.df:
    #             self.df['flag_rollover'] = 1
    #             self.df['prev_sal'] = self.df['SALINITY'].shift(1)
    #             self.df.loc[(abs(self.df['SALINITY'] - self.df['prev_sal']) > 0.1) & (self.df['type'] == 3), ['flag_rollover', 'flag']] = 4
    #             self.df = self.df.drop(columns=['prev_sal'])

    # 11. Stuck value test
    # Looks if there are temperature or salinity measurements identical
    ## Temperature
    def stuck(self):
        self.df['flag_temp_stuck'] = 1
        self.df['prev_temp_1'] = self.df['TEMPERATURE'].shift(1)
        self.df['prev_temp_2'] = self.df['TEMPERATURE'].shift(2)
        self.df['post_temp_1'] = self.df['TEMPERATURE'].shift(-1)
        self.df['post_temp_2'] = self.df['TEMPERATURE'].shift(-2)
        self.parse_segments()
        self.df.loc[((self.df['prev_temp_1'] == self.df['TEMPERATURE']) & (
                    self.df['post_temp_1'] == self.df['TEMPERATURE']) & (self.df['type'] != 3)), ['flag_temp_stuck',
                                                                                                  'flag']] = 3
        self.df.loc[((self.df['prev_temp_1'] == self.df['TEMPERATURE']) & (
                self.df['post_temp_1'] == self.df['TEMPERATURE']) & (
                             self.df['prev_temp_2'] == self.df['TEMPERATURE']) & (
                             self.df['post_temp_2'] == self.df['TEMPERATURE']) & (self.df['type'] != 3)), [
                        'flag_temp_stuck', 'flag']] = 4
        self.df = self.df.drop(columns=['prev_temp_1', 'post_temp_1', 'prev_temp_2', 'post_temp_2'])

        if 'SALINITY' in self.df:
            self.df['flag_sal_stuck'] = 1
            self.df['prev_sal_1'] = self.df['SALINITY'].shift(1)
            self.df['prev_sal_2'] = self.df['SALINITY'].shift(2)
            self.df['post_sal_1'] = self.df['SALINITY'].shift(-1)
            self.df['post_sal_2'] = self.df['SALINITY'].shift(-2)
            self.df.loc[
                ((self.df['prev_sal_1'] == self.df['SALINITY']) & (self.df['post_sal_1'] == self.df['SALINITY']) & (
                        self.df['type'] != 3)), ['flag_sal_stuck', 'flag']] = 3
            self.df.loc[((self.df['prev_sal_1'] == self.df['SALINITY']) & (
                    self.df['post_sal_1'] == self.df['SALINITY']) & (self.df['prev_sal_2'] == self.df['SALINITY']) & (
                                 self.df['post_sal_2'] == self.df['SALINITY']) & (
                                 self.df['type'] != 3)), ['flag_sal_stuck', 'flag']] = 4
            self.df = self.df.drop(columns=['prev_sal_1', 'post_sal_1', 'prev_sal_2', 'post_sal_2'])

        self.df = self.df.drop(columns=['vel', 'vel_smooth', 'delta_time', 'type'])

    # 12. Rate of change test
    # Excessive rise/fall test.
    # This test inspects the time series for a time rate of change that exceeds a threshold value identified by the
    # operator. T, SP, C, P values can change substantially over short periods in some locations, hindering the value of
    # this test. A balance must be found between a threshold set too low, which triggers too many false alarms, and one
    # set too high, making the test ineffective. Determining the excessive rate of change is left to the local operator.
    # The following shows two different examples of ways to select the thresholds provided by QARTOD VI participants.
    # Implementation of this test can be challenging. Upon failure, it is unknown which of the points is bad. Further, upon
    # failing a data point, it remains to be determined how the next iteration can be handled.
    # This test should be applied with different SDs for Up & Down and Bottom.
    # No flag fail (4) for this test, only suspect marking

    # Temp

    def rate_of_change(self):
        self.df['flag_RoC'] = 1
        self.parse_segments()

        sd_temp_down = self.df[self.df['type'] == 2]['TEMPERATURE'].std()
        sd_temp_bottom = self.df[self.df['type'] == 3]['TEMPERATURE'].std()
        sd_temp_up = self.df[self.df['type'] == 1]['TEMPERATURE'].std()

        n_dev = 3  # threshold

        self.df['prev_temp'] = self.df['TEMPERATURE'].shift(1)

        # check diffent flags

        self.df.loc[
            (abs(self.df['TEMPERATURE'] - self.df['prev_temp']) > (n_dev * sd_temp_down)) & (self.df['type'] == 2), [
                'flag_RoC', 'flag']] = 3
        self.df.loc[
            (abs(self.df['TEMPERATURE'] - self.df['prev_temp']) > (n_dev * sd_temp_bottom)) & (self.df['type'] == 3), [
                'flag_RoC', 'flag']] = 3
        self.df.loc[
            (abs(self.df['TEMPERATURE'] - self.df['prev_temp']) > (n_dev * sd_temp_up)) & (self.df['type'] == 1), [
                'flag_RoC', 'flag']] = 3

        if 'SALINITY' in self.df:
            sd_sal_down = self.df[self.df['type'] == 2]['SALINITY'].std()
            sd_sal_bottom = self.df[self.df['type'] == 3]['SALINITY'].std()
            sd_sal_up = self.df[self.df['type'] == 1]['SALINITY'].std()

            n_dev = 3  # threshold

            self.df['prev_sal'] = self.df['SALINITY'].shift(1)

            # check diffent flags

            self.df.loc[(abs(self.df['SALINITY'] - self.df['prev_sal']) > (n_dev * sd_sal_down)) & (
                    self.df['type'] == 2), ['flag_RoC', 'flag']] = 3
            self.df.loc[(abs(self.df['SALINITY'] - self.df['prev_sal']) > (n_dev * sd_sal_bottom)) & (
                    self.df['type'] == 3), ['flag_RoC', 'flag']] = 3
            self.df.loc[(abs(self.df['SALINITY'] - self.df['prev_sal']) > (n_dev * sd_sal_up)) & (
                    self.df['type'] == 1), ['flag_RoC', 'flag']] = 3

            self.df = self.df.drop(columns=['prev_sal'])

        self.df = self.df.drop(columns=['prev_temp'])

    # 13. Timing/gap test
    # Check for the arrival of data: Test determines that the most recent data point has been measured and received within the expected time
    # window (TIM_INC) and has the correct time stamp (TIM_STMP).

    def timing_gap(self):
        self.df['flag_timing_gap'] = 1
        currdate = datetime.utcnow()
        tim_inc = 24  # hours
        time_gap = currdate - self.df['DATETIME'].iloc[-1]
        if time_gap.total_seconds() / 3600 > tim_inc:
            self.df['flag_timing_gap'] = 3
            self.df['flag'] = 3

    # 14. Climatology test
    # Test that data point falls within seasonal expectations.
    # This test is a variation on the gross range check, where the thresholds T_Season_MAX and T_Season_MIN are
    # adjusted monthly, seasonally, or at some other operator-selected time period (TIM_TST). Expertise of the operator
    # is required to determine reasonable seasonal averages. Longer time series permit more refined identification of
    # appropriate thresholds. The ranges should also vary with water depth, if the measurements are taken at sites that
    # cover significant vertical extent and if climatological ranges are meaningfully different at different depths (e.g.,
    # narrower ranges at greater depth).
    # Because of the dynamic nature of T and S in some
    # locations, no fail flag is identified for this test.
    # Set limits for all areas, preferably also changing according to season.
    # In the mean time just take min and max of temp and sal of all measurements from our vessels in DB.

    # Temp and sal

    def climatology(self):
        # list contains first tuple (Temp) and second tuple (Sal)
        d = {'Red Sea': [(21.7, 40), (2, 41)], 'Mediterranean Sea': [(10, 40), (2, 40)],
             'North Western Shelves': [(-2, 24), (0, 37)], 'South West Shelves': [(-2, 30), (0, 38)],
             'Artic Sea': [(-1.92, 25), (2, 40)], 'Atlantic': [(2, 40), (2, 38)], 'North Sea': [(2, 40), (2, 38)]}

        self.df['flag_clima'] = 1
        self.df.loc[
            ((self.df['TEMPERATURE'] < d[self.zone][0][0]) | (self.df['TEMPERATURE'] > d[self.zone][0][1])), 'flag_clima'] = 3

        if 'SALINITY' in self.df:
            self.df.loc[
                ((self.df['SALINITY'] < d[self.zone][1][0]) | (self.df['SALINITY'] > d[self.zone][1][1])), 'flag_clima'] = 3

    def drift(self):
        # time and location boundaries
        self.df['flag_drift'] = 1
        self.parse_segments()

        df_bottom = self.df[self.df['type'] == 3].reset_index(drop=True)
        if len(df_bottom) != 0:
            temp1 = df_bottom['TEMPERATURE'].iloc[0]
            temp2 = df_bottom['TEMPERATURE'].iloc[-1]
            if ((df_bottom['DATETIME'].iloc[-1] - df_bottom['DATETIME'].iloc[0]).seconds / 3600) < 24:
                if abs(temp1 - temp2) > 3:
                    self.df.loc[:, ['flag_drift', 'flag']] = 3
                if 'SALINITY' in self.df:
                    sal1 = df_bottom['SALINITY'].iloc[0]
                    sal2 = df_bottom['SALINITY'].iloc[-1]
                    if abs(sal1 - sal2) > 8:
                        self.df.loc[:, ['flag_drift', 'flag']] = 3

    def parse_segments(self):
        self.df['DATETIME'] = pd.to_datetime(self.df['DATETIME'])
        self.df['DATEINT'] = (self.df['DATETIME'] - self.df['DATETIME'].min())
        self.df['DATEINT'] = self.df.apply(lambda row: row['DATEINT'].total_seconds(), axis=1)
        self.df['PRESSURE'] = self.df['PRESSURE'].astype(float)
        self.df['GAP_PRESSURE'] = abs(self.df['PRESSURE'] - self.df['PRESSURE'].quantile(0.9))

        self.df['delta_time'] = self.df['DATETIME'].diff(periods=-1) / pd.offsets.Second(1)
        self.df['vel'] = self.df['PRESSURE'].diff(periods=-1) / self.df['delta_time'] * 1000
        self.df['vel_smooth'] = self.df['vel'].rolling(7, center=True, min_periods=1).mean()

        self.df['type'] = 3

        # True down and False up
        self.df['direction'] = self.df['PRESSURE'].shift(1) < self.df['PRESSURE']
        self.df['dir'] = self.df['direction'].rolling(10, center=True, min_periods=1).mean()

        # Direction and pressure
        self.df.loc[(self.df['dir'] > 0.5) & (self.df['GAP_PRESSURE'] > 0.5 * self.df['GAP_PRESSURE'].max()), 'dir'] = 1
        self.df.loc[(self.df['dir'] < 0.5) & (self.df['GAP_PRESSURE'] > 0.5 * self.df['GAP_PRESSURE'].max()), 'dir'] = 0

        self.df.loc[
            (self.df['dir'] == 1) & (self.df['GAP_PRESSURE'] > 0.5 * self.df['GAP_PRESSURE'].max()), 'direction'] = True
        self.df.loc[(self.df['dir'] == 0) & (
                    self.df['GAP_PRESSURE'] > 0.5 * self.df['GAP_PRESSURE'].max()), 'direction'] = False

        std_bottom = self.df[(self.df['DATETIME'] > self.df['DATETIME'].quantile(0.1)) & (
                    self.df['DATETIME'] < self.df['DATETIME'].quantile(0.9))]['PRESSURE'].std()

        nodown, noup = False, False
        if std_bottom < 0.2:
            # Smooth size to find the inflection point
            min_seg_size = 1
            max_down_pressure = self.df['PRESSURE'].iloc[:min_seg_size].max()
            while max_down_pressure < 0.9 * self.df['PRESSURE'].max():
                min_seg_size += 1
                max_down_pressure = self.df['PRESSURE'].iloc[:min_seg_size].max()

            if min_seg_size == 1:
                nodown = True

            min_seg_size = 1
            max_up_pressure = self.df['PRESSURE'].iloc[-min_seg_size:].max()
            while max_up_pressure < 0.9 * self.df['PRESSURE'].max():
                min_seg_size += 1
                max_up_pressure = self.df['PRESSURE'].iloc[-min_seg_size:].max()

            if min_seg_size == 1:
                noup = True

        else:
            # Smooth size to find the inflection point
            min_seg_size = 1
            max_down_pressure = self.df['PRESSURE'].iloc[:min_seg_size].max()
            while max_down_pressure < 0.5 * self.df['PRESSURE'].max():
                min_seg_size += 1
                max_down_pressure = self.df['PRESSURE'].iloc[:min_seg_size].max()

            min_seg_size = 1
            max_up_pressure = self.df['PRESSURE'].iloc[-min_seg_size:].max()
            while max_up_pressure < 0.5 * self.df['PRESSURE'].max():
                min_seg_size += 1
                max_up_pressure = self.df['PRESSURE'].iloc[-min_seg_size:].max()

        self.df.loc[:min_seg_size, 'direction'] = True
        self.df.loc[len(self.df) - min_seg_size:, 'direction'] = False

        lim_pressure = self.df[~self.df['direction']].iloc[0], self.df[self.df['direction']].iloc[-1]

        self.df.loc[:lim_pressure[0].name - 1, 'type'] = 2
        self.df.loc[lim_pressure[1].name + 1:, 'type'] = 1

        if nodown:
            self.df.loc[self.df['type'] == 2, 'type'] = 3

        if noup:
            self.df.loc[self.df['type'] == 1, 'type'] = 3
