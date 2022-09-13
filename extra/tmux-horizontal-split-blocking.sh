#!/bin/sh
# Uses unique tmux wait-for channel based on time with nanoseconds
# Inspired by cjpbirkbeck's example @ https://github.com/pazz/alot/issues/1560#issuecomment-907222165

IFS=' '

# Ensure we're actually running inside tmux:
if [ -n "$TMUX" ]; then
    fin=$(date +%s%N)
    # Use new-window to create a new window instead.
    tmux split-window -h "${*}; tmux wait-for -S ${fin}"
    tmux wait-for "${fin}"
else
    # You can replace xterm with your preferred terminal emulator.
    xterm -e "${*}"
fi

