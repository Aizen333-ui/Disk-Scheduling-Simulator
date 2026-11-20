# Disk Scheduling Simulator

Simulates nine disk scheduling algorithms on a time-based disk model and compares
head movement, waiting/response time, starvation and fairness.

Algorithms: FCFS, SSTF, SCAN, C-SCAN, LOOK, C-LOOK, N-step SCAN, FSCAN, and a
simplified model of Linux's mq-deadline scheduler (DEADLINE).

## Setup
    pip install -r requirements.txt     # Tkinter ships with Python on Windows/macOS
    (Linux: sudo apt install python3-tk)

## Run
    python gui.py                                   # graphical interface
    python cli.py --requests 98 183 37 122 14 124 65 67 --head 53 --size 200
    python cli.py --requests 98@0 183@5 37@8 --head 53 --algorithms FCFS SSTF LOOK
    python experiment.py --workload hotspot --trials 300 --requests 30 --gap 8
    python -m unittest -v                           # run all tests

Requests are cylinders, optionally with an arrival time: `98` or `98@12.5` (ms).

## How it works
- **Time model** (`disk_model.py`): service time = seek (grows with sqrt of distance,
  1 ms to 15 ms by default) + rotational latency (half a rotation at 7200 RPM, or random)
  + transfer time.
- **Engine** (`engine.py`): requests arrive over time; the policy picks the next request
  or an edge/return-jump move. Reports total head movement, wait time, response time,
  maximum wait (starvation), Jain fairness index, throughput and utilisation.
- **Workloads** (`workloads.py`): uniform, sequential, hotspot, a starvation demo, and
  CSV import/export (`arrival_ms,cylinder`).
- **Experiments** (`experiment.py`, `stats.py`): many random trials, paired across
  algorithms, summarised as mean with 95% confidence interval plus box plots.

## Notes and limits
- Results in milliseconds come from the model above, not from a real drive.
- DEADLINE is simplified: one FIFO queue with an expiry time, served in batches over a
  sorted queue. It omits read/write separation and request merging. Default expiry is
  100 ms (Linux's default read expiry is 500 ms) because simulated workloads are short.
- With all requests at time 0, results match the classic textbook examples
  (e.g. FCFS 640, SSTF 236, C-SCAN 382 for the Silberschatz et al. queue).

## Files
- `gui.py` interface; `cli.py` command line; `experiment.py` random experiments
- `engine.py` algorithms and metrics; `disk_model.py` timing; `workloads.py` workloads and CSV
- `stats.py` statistics; `plots.py` charts; `inputs.py` input parsing
- `disk_scheduling.py` original static algorithms (kept as a reference for the tests)
- `test_*.py` unit tests
