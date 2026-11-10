#!/usr/bin/env bash
# Stop the lane's connected stack started by stack-up.sh. Usage: RUN=<dir> stack-down.sh
RUN=${RUN:?}
[ -f "$RUN/pids" ] && while read -r pid; do kill "$pid" 2>/dev/null; done < "$RUN/pids"
sleep 1
[ -f "$RUN/pids" ] && while read -r pid; do kill -9 "$pid" 2>/dev/null; done < "$RUN/pids"
rm -f "$RUN/pids"
echo "stopped"
