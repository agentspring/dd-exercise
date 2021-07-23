#!/usr/bin/python
# Last Update: 2021-07-23 Dave Gerhard
#
# Report status of Moogsoft Enterprise moolets
#
# Processes output of Graze 'getSystemStatus'
# Checks:
# - running
# - missed_heartbeats
# - message_queue
#
# Setup:
# Adjust the below connect settings
# Adjust thresholds
# Understand the dependancies on system.conf
#
# NOTES:
# The status reported by getSystemStatus relies on a properly configured
# processes[{}] section of system.conf.
#
# If system.conf is not properly configured to represent the expected
# active processes then getSystemStatus can report false positives or
# it can miss when required processes are not running.
#
# If system.conf is not going to be configured properly then the other
# option would be to maintain the 'expected' process list here and check
# the output against that.
#
# * getSystemStatus provide similar results to ha_cntl -v with additional
#   metrics as seen in UI Self Monitoring
# 
import json
import sys
import urllib2, ssl
import base64

# Datadog specific
from datadog import initialize, statsd

options = {
    'statsd_host':'192.168.124.179',
    'statsd_port':8125
}
initialize(**options)

# Call Graze API getSystemStatus
try:
    username="graze"
    password="graze"
    url="https://192.168.124.179:8443/graze/v1/getSystemStatus"
    request = urllib2.Request(url)
    base64string = base64.b64encode('%s:%s' % (username, password))
    request.add_header("Authorization", "Basic %s" % base64string)   
    result = urllib2.urlopen(request, context=ssl._create_unverified_context())
    getSystemStatus = result.read() 
    #print "results:\n" + getSystemStatus
except IOError, e:
    if hasattr(e, 'code'): # HTTPError
        print 'http error code: ', e.code
    elif hasattr(e, 'reason'): # URLError
        print "can't connect, reason: ", e.reason
    else:
        raise
    #Send Notification - unable to connect - retry
    sys.exit(1)

#---------------------------------------------------------------
# Thresholds
#---------------------------------------------------------------
MISSED_HEARTBEATS_THRESHOLD=5 #heartbeats updated every 10 sec

# If message_queue is greater than value indicated -> thats bad
# Adjust moolets to watch and the thresholds
# (Should support exceeded X times)
QUEUE_THRESHOLDS = {
   "AlertBuilder": -1, #-1 used for testing
   "Alert Workflows": 10,
   "Enricher": 75,
   "MaintenanceWindowManager": 5
} 

# Arrays to hold moolets with issues
notRunning = [];
missedHeartbeats = [];
exceededQueueMax = [];

#Use below if processing from file passed at arg1
#file = sys.argv[1]
#data = json.load(open(file))

#---------------------------------------------------------------
# Process output of getSystemStatus
#---------------------------------------------------------------
data = json.loads(getSystemStatus)
#print data["processes"][0]["display_name"]
for process in data["processes"]:
    p_name = process["display_name"]
    p_status  = process["running"]
    #print str(p_status) + "\t" + p_name
    if p_status == False:
        notRunning.append(p_name)
        continue

    # Check status of moog_farmd moolets (sub_components)
    if p_name == "moog_farmd":
        
        # Check status and missed_heartbeats for all moolets
        for subcomp in process["sub_components"]:
            moolet_status = process["sub_components"][subcomp]["running"]
            # If moolet configured to not run on startup missed_heartbeats wont exist
            moolet_missed_hbs = 0
            if "missed_heartbeats" in process["sub_components"][subcomp]:
                moolet_missed_hbs = process["sub_components"][subcomp]["missed_heartbeats"]
            #print "moolet" + "." + subcomp +"\t" + str(moolet_status) + "\t" + "missed_heartbeats: " + str(moolet_missed_hbs)
            if moolet_status == False:
                notRunning.append(subcomp)
            if moolet_missed_hbs > MISSED_HEARTBEATS_THRESHOLD:
                missedHeartbeats.append(subcomp)
            continue
        
        # Check message_queues
        if "message_queues" not in process["additional_health_info"]:
            continue
        for subcomp in process["additional_health_info"]["message_queues"]:
            msg_queue = process["additional_health_info"]["message_queues"][subcomp].split("/")[0]
            msg_queue_len = int(msg_queue) 
            # Check if there is a threshold set for this moolet
            if subcomp in QUEUE_THRESHOLDS:
                if msg_queue_len > QUEUE_THRESHOLDS[subcomp]:
                    exceededQueueMax.append(subcomp)
                #print "moolet" + "." + subcomp +"\t" + str(msg_queue_len) + " threshold = " + str(QUEUE_THRESHOLDS[subcomp])
            continue
    # Done if moog_farmd

# Problems
not_running = len(notRunning)
statsd.gauge('dogstatsd.moog.systemstatus.moolets_not_running', not_running, tags=["service:farmd", "moolets:"+":".join(map(str, notRunning))])

missedhb = len(missedHeartbeats)
statsd.gauge('dogstatsd.moog.systemstatus.moolets_missed_hb', missedhb, tags=["service:farmd", "moolets:"+":".join(map(str, missedHeartbeats))])

exceeded_q_max = len(exceededQueueMax)
statsd.gauge('dogstatsd.moog.systemstatus.moolets_queue_exceeded', exceeded_q_max, tags=["service:farmd", "moolets:"+":".join(map(str, exceededQueueMax))])

# Raw Metrics
ab_mp = data["processes"][0]["additional_health_info"]["messages_processed"]["AlertBuilder"];
smgr_mp = data["processes"][0]["additional_health_info"]["messages_processed"]["SituationMgr"];
epm = data["processes"][0]["additional_health_info"]["event_processing_metric"]
rest_in = data["processes"][2]["additional_health_info"]["ingested_events"]["last_minute"];

#print "alertbuilder="+str(ab_mp) + " restlam="+str(rest_in) + " smgr=" + str(smgr_mp) + " epm="+str(epm)

statsd.gauge('dogstatsd.moog.systemstatus.alertbuilder_epm', ab_mp, tags=["service:farmd"])
statsd.gauge('dogstatsd.moog.systemstatus.situationmgr_epm', smgr_mp, tags=["service:farmd"])
statsd.gauge('dogstatsd.moog.systemstatus.restlam_epm', rest_in, tags=["service:farmd"])
statsd.gauge('dogstatsd.moog.systemstatus.event_processing_time', epm, tags=["service:farmd"])

sys.exit(0);
