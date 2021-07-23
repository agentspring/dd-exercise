#!/usr/sbin/python 
from datadog import initialize, statsd
import time

options = {
    'statsd_host':'192.168.124.179',
    'statsd_port':8125
}

initialize(**options)

i = 0

while(1):
  i += 1
  print "sending" + str(i)
  statsd.gauge('example_metric.gauge', i, tags=["env:dev", "app:statd"])
  time.sleep(10)
