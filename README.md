# BDC_QC
Collection of manuals and scripts to assist in automated quality assurance and quality control for oceanographic data collected via fishing gear as a platform.

## Manual QC

Fishing gear as a platform for sensors:

Implementation of real-time quality control of in-situ temperature and salinity data collected via fishing gear

Version 1

November 2020

## Table of contents

<!--ts-->

* [Introduction](#introduction)
* [Flags](#flags)
* [Real-time Quality control](#real-time-quality-control)
	* [Fisheries quality control tests](#fisheries-quality-control-tests)
		* [Platform identification (under development)](#platform-identification-under-development)
		* [Vessel ID control (under development)](#vessel-id-control-under-development)
		* [Gear type control (under development)](#gear-type-control-under-development)
	* [Quality control tests CTD](#quality-control-test-ctd)
		* [Impossible date test](#impossible-date-test)
		* [Impossible location test](#impossible-location-test)
		* [Position on land test](#position-on-land-test)
		* [Impossible speed test (MOBILE GEAR)](#impossible-speed-test-mobile-gear)
		* [Global range test](#global-range-test)
		* [Spike test](#spike-test)
		* [Digit rollover test](#digit-rollover-test)
		* [Stuck value / flat line test](#stuck-value-flat-line-test)
		* [Rate of change test](#rate-of-change-test)
		* [Timing / gap test](#timing-gap-test)
		* [Climatology test](#climatology-test)
		* [Drift test (under development)](#drift-test-under-development)
	* [Quality control tests oxygen / turbidity (under development)](#quality-control-tests-oxygen-turbidity-under-development)
* [Delayed-mode Quality control (under development)](#delayed-mode-quality-control-under-development)
* [Quality control tests (under development)](#quality-control-tests-under-development)
* [References](#references)

<!--te-->




## Introduction

This document describes the implementation of the automated checks that are performed on CTD (Conductivity, Temperature, Depth) data that are collected via fishing gear as a platform for sensors. Trajectory data describe the positions and time of the fishing vessel.

<p align="center">

![BDC concept](https://user-images.githubusercontent.com/70140203/100598077-88045780-32fe-11eb-935d-c67de78713d9.png)

Figure 1. A fishing vessel as a data collection platform.

</p>

<br>

## Flags

The data collected by fishing vessels of opportunity, i.e. with sensors attached to fishing gear, is aimed to be interoperable and used by different users with different requirements. In order to maximize (re)usability, the data is quality controlled and flagged to characterize data. Flags are always included in the data delivery, to optimize data reliability and consistency.

Quality checks are based on the tests described by IOOS (U.S. Integrated Ocean Observing System, 2020) and the Argo network (Wong et al., 2020).

The flags used by BDC to indicate QC status are based on existing standards defined by other programs and datasets for oceanographic observations. Flags are indicated in table 1.


<p align="center">

| **Code** | **Meaning** |
| :---: | :---: |
| 0/NA | No QC was performed |
| 1 | Good data |
| 3 | Suspect data |
| 4 | Bad data |
| 5 | Corrected data |
| 9 | Missing value |

<p align="center">

Table 1. Quality flags.

- Data flagged as (0) are not quality controlled, and therefore recommended not to be used without QC performed by the user.
- Data flagged as (1) have been quality controlled, and can be used safely.
- Data flagged as (3) have been quality controlled, and marked as suspect. These data can&#39;t be used directly, but have the potential to be corrected in delayed mode.
- Data flagged as (4) have been quality controlled and should be rejected.
- Data flagged as (5) have been corrected.
- Data flagged as (9) are missing.

<br>

## Real-time Quality control

![schematics](https://user-images.githubusercontent.com/70140203/100599274-175e3a80-3300-11eb-927c-fc7ebc2ca4f6.png)

Figure 2. Schematic of the data flow applied to oceanographic data from fishing vessels.

<br>

### 3.1. Fisheries quality control tests

<br>

#### Platform identification (under development)

Check if there is an unknown sensor ID/Vessel ID

<br>

#### Vessel ID control (under development)

Check if the vessel is operating in an expected region.

| **Region** | **Longitude min** | **Longitude max** | **Latitude min** | **Latitude max** |
| :---: | :---: | :---: | :---: | :---: |
| **Greenland** | -60 | -15 | 55 | 90 |
| **North Sea and Baltic** | -15 | 30 | 45 | 60 |
| **Atlantic** | -75 | 30 | 55 | 90 |
| **New Zealand** | 160 | 185 (on a 0-360 degree scale) or -175 (on a -180-180 scale) | -50 | -30 |
| **Alaska** | -180 | -125 | 45 | 90 |

<br>

#### Gear type control (under development)

Check if the gear type assigned is correct. Distance is calculated between the first and last data locations.

| **Flags** | **Description** |
| :---: | :---: |
| Suspect (3) | _Gear type is considered suspect. <br><br> Fixed: distance &gt; 200 meters <br> Mobile: distance &lt;= 200 meters_ |
| Pass (1) | _Applies for test pass condition._ |

<br>

### 3.2. Quality control tests CTD

<br>

#### Impossible date test

The date of the profile can be no earlier than 01/01/2010 and no later than current date in UTC

| **Flags** | **Description** |
| :---: | :---: |
| Fail (4) | _Impossible date: <br><br> 01/01/2010 &lt; Date &gt; UTC_ |
| Pass (1) | _Applies for test pass condition._ |

<br>

#### Impossible location test

This simple test controls whether the geographic location is sensible, based on the global limits for longitude and latitude.

| **Flags** | **Description** |
| :---: | :---: |
| Fail (4) | _Impossible location: <br><br> -180 &lt; longitude &gt; 180 <br> -90 &lt; latitude &gt; 90_ |
| Pass (1) | _Applies for test pass condition._ |

<br>

#### Position on land test

This test requires that the observation latitude and longitude from a float profile be located in an ocean. In this case a 5 minute bathymetry file (ETOPO5/TerrainBase) downloaded from [http://www.ngdc.noaa.gov/mgg/global/etopo5.html](http://www.ngdc.noaa.gov/mgg/global/etopo5.html) is used.

| **Flags** | **Description** |
| :---: | :---: |
| Fail (4) | _Measurement is on land._ |
| Pass (1) | _Applies for test pass condition._ |

<br>

#### Impossible speed test (MOBILE GEAR)

This test controls whether there are no erroneous locations provided. The speed of the vessels are generated given the positions and times of the vessel. Vessel speed is expected not to exceed 3 ms−1. Otherwise, it means either the positions or times are bad data, or a vessel is sailing full speed rather than fishing.

This test is helpful for determining if there is an error in merging the sensor and GPS data, often due to setting a sensor to a time zone other than UTC.

| **Flags** | **Description** |
| :---: | :---: |
| Fail (4) | _Speed is too high for mobile gear fishing. <br><br> Vessel speed &gt; 4.12 ms−1 (8 knots)_ |
| Pass (1) | _Applies for test pass condition._ |

<br>

#### Global range test

Gross filter on the observed values of pressure, temperature and salinity based on the sensor ranges (NKE TD, NKE CTD and ZebraTech Moana TD).

This test applies a gross filter on the observed values of pressure, temperature and salinity.

| **Flags** | **Description** |
| :---: | :---: |
| Fail (4) | _Measurement outside sensor operating range <br><br> -5 &lt; Pressure <br> -2 &lt; Temperature &gt; 35 °C <br> 2 &lt; Salinity &gt; 42 PSU_ |
| Suspect (3) | -5 &lt;= Pressure &lt; 0<br> Pressure &gt; Max sensor depth + 10% |
| Pass (1) | _Applies for test pass condition._ |

<br>

####

<br>

#### Spike test

The spike tests checks whether there is a significant difference between sequential measurements, by comparing a measurement to its adjacent ones. The test does not consider differences in pressure, and rather assumes measurements that adequately reproduce changes in temperature and salinity with pressure.

Here, V2 is the tested value, and V1 and V3 are the values before and after. Spikes consisting of more than one data point are difficult to capture, but their onset may be flagged by the rate of change test.

Cut-off values are based on (Wong et al., 2020), and V2 will be flagged based on the following values.

| **Flags** | **Description** |
| :---: | :---: |
| Fail (4) | _Measurement differs significantly from its neighbours <br><br> Pressure &lt; 500 dbar:<br> Test value T &gt; 6.0 °C <br> Test value S &gt; 0.9 PSU <br><br> Pressure &gt; = 500 dbar: <br> Test value T &gt; 2.0°C <br>Test value S &gt; 0.3 PSU_ |
| Pass (1) | _Applies for test pass condition._ |

<br>

#### Digit rollover test

This is a special version of the spike test, which compares the measurements at the end of the profile to the adjacent measurement. Temperature at the bottom should not differ from the adjacent measurement by more than 1°C. Action: Values that fail the test should be flagged as bad data.

| **Flags** | **Description** |
| :---: | :---: |
| Fail (4) | _Measurement differs significantly from its neighbours <br><br> T2 - T1 &gt; 1.0 °C_ |
| Pass (1) | _Applies for test pass condition._ |

<br>

#### Stuck value/ flat line test

It is possible that, when sensors fail, continuously repeated observations of the same value are produced. In this test, the present observation is compared to several previous observations. The present observation is flagged if the present observation is the same as all previous observations, calculating in a tolerance value.

| **Flags** | **Description** |
| :---: | :---: |
| Fail (4) | _The five most recent observations are equal <br><br> Tolerance values: <br> Temperature: 0.05 °C <br> Salinity: 0.05 PSU <br> Pressure: 0.5 dbar_ |
| Suspect (3) | _The three most recent observations are equal_ |
| Pass (1) | _Applies for test pass condition._ |

<br>

####

<br>

#### Rate of change test

This test is applied per segment (Up-Down-Bottom), and inspects the segments on a rate of change exceeding a threshold defined by the operator. In this case the thresholds are based on the IOOS examples (U.S. Integrated Ocean Observing System, 2020), where the rate of change between measurement Tn-1 and Tn must be less than three standard deviations (3\*SD). The SD of the T time series is computed over the full segment.

This test needs to find a balance between setting a threshold too low, triggering too many false alarms, and setting a threshold too high, triggering too little alarms.

Measurements failing this test are marked as suspect (3).

| **Flags** | **Description** |
| :---: | :---: |
| Suspect (3) | _The rate of change exceeds the selected threshold._ |
| Pass (1) | _Applies for test pass condition._ |

<br>

####

<br>

#### Timing/gap test

This test controls whether the most recent measurement has been received within the expected time period.

Measurements failing this test are only marked as suspect, to be controlled later.

| **Flags** | **Description** |
| :---: | :---: |
| Suspect (3) | _Check for the arrival of data <br><br> Data didn&#39;t come in as expected: NOW – TIM\_STMP &gt; TIM\_INC_ |
| Pass (1) | _Applies for test pass condition._ |

<br>

#### Climatology test

Test that data point falls within seasonal expectations according to different regions.

This test is a variation on the gross range check, where the thresholds T\_Season\_MAX and T\_Season\_MIN are adjusted monthly, seasonally, or at some other operator-selected time period (TIM\_TST) in a specific region. Because of the dynamic nature of T and S in some locations, no fail flag is identified for this test and measurements will only be marked as &#39;suspect&#39;.

Regional ranges are defined as the following ([https://archimer.ifremer.fr/doc/00251/36230/34790.pdf](https://archimer.ifremer.fr/doc/00251/36230/34790.pdf)), as seen on the map below. Cornerpoints for the Red Sea and Mediterranean come from the Argo manual.

![clima](https://user-images.githubusercontent.com/70140203/100601137-8341a280-3302-11eb-83da-4dd1b9ada1a9.jpg)

Red Sea

- Temperature in range 21.7°C to 40.0°C
- Salinity in range 2.0 to 41.0

Mediterranean Sea

- Temperature in range 10.0°C to 40.0°C
- Salinity in range 2.0 to 40.0

North Western Shelves (from 60 N to 50 N and 20 W to 10 E)

- Temperature in range –2.0°C to 24.0°C
- Salinity in range 0.0 to 37.0

South West Shelves (From 25 N to 50 N and 30 W to 0 W)

- Temperature in range –2.0°C to 30.0°C
- Salinity in range 0.0 to 38.0

Arctic Sea (above 60N)

- Temperature in range –1.92°C to 25.0°C
- Salinity in range 2.0 to 40.0

Seasonal limits per area still have to be defined, in the meantime we take min and max of temp and sal of all measurements from our vessels in DB.

| **Flags** | **Description** |
| :---: | :---: |
| Suspect (3) | _Measurement outside climatology range <br><br> Seas\_min\_T &lt; Temperature&gt; Seas\_max\_T <br> Seas\_min\_S &lt; Salinity &gt; Seas\_max\_S_ |
| Pass (1) | _Applies for test pass condition._ |

<br>

#### Drift test (under development)

<br>

### 3.3. Quality control tests oxygen/turbidity

Under development

<br>

## Delayed-mode quality control

<br>

### 4.1. Quality control tests

Under development

<br>

## References

Annie Wong, Robert Keeley, Thierry Carval and the Argo Data Management Team (2020).

Argo Quality Control Manual for CTD and Trajectory Data. [http://dx.doi.org/10.13155/33951](http://dx.doi.org/10.13155/33951)

U.S. Integrated Ocean Observing System, 2020. Manual for Real-Time Quality Control of In-situ Temperature and Salinity Data Version 2.1: A Guide to Quality Control and Quality Assurance of In-situ Temperature and Salinity Observations. 50 pp. [https://doi.org/10.25923/x02m-m555](https://doi.org/10.25923/x02m-m555)

EuroGOOS DATA-MEQ working group (2010). Recommendations for in-situ data Near Real Time Quality Control. https://doi.org/10.13155/36230