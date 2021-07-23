#!/bin/bash
#
# Track size of the rabbitmq dir in Megabytes
#
RABBIT_DIR=$MOOGSOFT_HOME/var/lib/rabbitmq
DD_API_KEY=90e5925495e61452b1f4b958ec1ba7e0

UTCTIME=$(date +%s) #Current time (UTC/GMT)

# Function sends timeseries data to Datadog
sendToDatadog() {
   curl -X POST "https://api.datadoghq.com/api/v1/series" -H "Content-Type: application/json"  -H "DD-API-KEY: ${DD_API_KEY}"  -d @- << EOF
 {
  "series": [
    {
      "host": "moog",
      "metric": "api.moog.rabbitmq.mnesia_size",
      "points": [
        [
          "${UTCTIME}",
          "$1"
        ]
      ],
      "tags": [
         "app:moog", "service:rabbitmq", "env:dev",
         "affected_apps:moog", "affected_services:apache-tomcat,farmd"
      ],
      "type": "gauge"
    }
  ]
}
EOF
}

# Verify path to rabbit nmesia is available
if [ ! -d $RABBIT_DIR ]; then
   notify "Could not find/read rabbitmq dir here: $RABBIT_DIR."
   exit 1
fi

dirSizeM=$(du -sm $MOOGSOFT_HOME/var/lib/rabbitmq | cut -f 1)
sendToDatadog $dirSizeM

exit

