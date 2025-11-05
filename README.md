usage: 

1. `start_socat.sh` - Simulates a pair of connected serial ports using `socat`

2. `script.py` - Listens on a virtual serial port and sends a random number whenever it receives the ? command.

3. example sending to virtual port:
```
# Sends '?' to the virtual serial port and shows the response.
cat < /dev/pts/2 &
echo -n "?" > /dev/pts/2
```
