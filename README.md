# Usage

```sh
./start_socat.sh  # replace /dev/pts/{1,2} with returned virtual devices from socat
python3 script.py /dev/pts/1
cat < /dev/pts/2 &
echo 'SWEEP 0 4095 256 0 4095 256' > /dev/pts/2
```
