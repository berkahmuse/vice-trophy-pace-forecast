# vice-trophy-pace-forecast

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/berkahmuse/vice-trophy-pace-forecast/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/berkahmuse/vice-trophy-pace-forecast/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

A printed trophy earn rate is a ratio — earners over players tracked — and the two sides move for different reasons. This forecaster works in count space: it collapses the recorded Exophase page history to its distinct states, fits the tracked-player count and each trophy's earner count separately on a log-time clock, shrinks every trophy's earner slope toward the page-wide median pace (a trophy with few earners has a noisy slope of its own), walks both fits from their last observed values to the target, and divides. Quantile spreads grow with the distance travelled, with 1/sqrt(earners), and with each trophy's disagreement with the pooled pace. When the page has only ever shown one state, a dilution fallback takes over: the coming refresh mostly adds fresh players, so medians sag and the bands stay wide.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=9wx1snxe&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>
