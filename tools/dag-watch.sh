#!/usr/bin/env bash
case "${1:-status}" in
    on)   launchctl load ~/Library/LaunchAgents/com.michaelnichols.dag-watch.plist 2>/dev/null
          echo "dag-watch: loading LaunchAgent..." ;;
    off)  launchctl unload ~/Library/LaunchAgents/com.michaelnichols.dag-watch.plist 2>/dev/null
          echo "dag-watch: unloading LaunchAgent..." ;;
    status) if launchctl list com.michaelnichols.dag-watch &>/dev/null; then
              echo "dag-watch: RUNNING"; echo "Log: ~/.grok/logs/dag-watch.log"
            else
              echo "dag-watch: STOPPED"
            fi ;;
    log)   tail -f ~/.grok/logs/dag-watch.log ;;
    *)     echo "Usage: dag-watch [on|off|status|log]" ;;
esac
