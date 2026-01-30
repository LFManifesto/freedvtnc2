# freedvtnc2-lfm Command Protocol

## Overview

freedvtnc2-lfm adds a TCP command interface on port 8002, inspired by VARA's architecture. This allows runtime control of the modem without restarting the service.

## Ports

| Port | Purpose | Protocol |
|------|---------|----------|
| 8001 | KISS TNC (data) | Binary KISS frames |
| 8002 | Command interface | ASCII commands |

## Command Format

- Commands are ASCII text, terminated with newline (`\n`)
- Commands are case-insensitive
- Arguments separated by space
- One command per line

## Commands

### MODE [DATAC1|DATAC3|DATAC4]

Set or query the TX modem mode.

```
> MODE DATAC3
< OK MODE DATAC3

> MODE
< OK MODE DATAC3

> MODE INVALID
< ERROR Invalid mode. Valid: DATAC1, DATAC3, DATAC4
```

### VOLUME [dB]

Set or query TX output volume in dB.

```
> VOLUME -6
< OK VOLUME -6

> VOLUME
< OK VOLUME -6

> VOLUME abc
< ERROR Invalid volume
```

### FOLLOW [ON|OFF]

Enable/disable auto mode following (TX matches last received mode).

```
> FOLLOW ON
< OK FOLLOW ON

> FOLLOW OFF
< OK FOLLOW OFF

> FOLLOW
< OK FOLLOW OFF
```

### STATUS

Query current modem status.

```
> STATUS
< OK STATUS MODE=DATAC3 VOLUME=0 FOLLOW=OFF PTT=OFF CHANNEL=CLEAR
```

### LEVELS

Query current audio input level.

```
> LEVELS
< OK LEVELS RX=-12.5
```

### PTT TEST

Trigger 2-second PTT test with tone.

```
> PTT TEST
< OK PTT TEST started
```

### CLEAR

Clear TX queues.

```
> CLEAR
< OK CLEAR
```

### SAVE

Save current config to ~/.freedvtnc2.conf.

```
> SAVE
< OK SAVE ~/.freedvtnc2.conf
```

### PING

Connection test.

```
> PING
< OK PONG
```

## Response Format

All responses start with `OK` or `ERROR`:

```
OK [command] [data]
ERROR [message]
```

## Connection Handling

- Server accepts multiple concurrent connections
- Each connection is independent
- No authentication required (local use only)
- Connection timeout: none (persistent until client disconnects)

## Example Session

```
$ nc localhost 8002
PING
OK PONG
STATUS
OK STATUS MODE=DATAC1 VOLUME=0 FOLLOW=OFF PTT=OFF CHANNEL=CLEAR
MODE DATAC3
OK MODE DATAC3
LEVELS
OK LEVELS RX=-15.2
VOLUME -3
OK VOLUME -3
STATUS
OK STATUS MODE=DATAC3 VOLUME=-3 FOLLOW=OFF PTT=OFF CHANNEL=CLEAR
```

## Integration with ReticulumHF

ReticulumHF portal connects to port 8002 to:
1. Change FreeDV mode without service restart
2. Adjust TX volume
3. Query status and levels
4. Enable/disable follow mode

This eliminates the need to restart freedvtnc2 for configuration changes.
