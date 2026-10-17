## Shell Command for running run_next_experiments.sh

```
cd <PRIVATE_PATH>
nano run_next_experiments.sh
chmod +x run_next_experiments.sh
nohup ./run_next_experiments.sh > experiment_queue_launcher.log 2>&1 &
disown
```


### Check Status
```
tail -f experiment_queue_launcher.log
```
