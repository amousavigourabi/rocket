# Reproduction package CSE3000 Atour

> This project is a part of the [Research Project](https://github.com/TU-Delft-CSE/Research-Project) 2025 in the Bachelor's Computer Science and Engineering at [TU Delft](https://https//github.com/TU-Delft-CSE).

The analyzer used to detect agreement violations and process the
statistics associated with the violations, time fitness, proposal
fitness, and their relationships is included as a Jupyter Notebook.

On the branches `atour-dcd`, `atour-nsga`, `atour-proposal-elitism`,
`atour-proposal-roulette`, `atour-proposal-tournament`,
`atour-random`, `atour-time-elitism`, `atour-time-roulette`, and
`atour-time-tournament`, the code and setup used to run the
experiments can be found. These branches correspond to the
following configurations described in my thesis.

| Branch | Configuration |
| --- | --- |
| `atour-random` | Baseline |
| `atour-time-elitism` | Elitist time |
| `atour-proposal-elitism` | Elitist proposal |
| `atour-time-roulette` | Roulette time |
| `atour-proposal-roulette` | Roulette proposal |
| `atour-time-tournament` | Tournament time |
| `atour-proposal-tournament` | Tournament proposal |
| `atour-dcd` | DCD tournament |
| `atour-nsga` | NSGA-II |

The raw result logs of the experiments are included under `./logs/`
in this branch, ready to be directly analyzed using the notebook
`analyzer.ipynb` without any further modifications.
