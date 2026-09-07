# Calendar Plan Inference

When the training calendar is unavailable, infer a safe session from the known
plan structure rather than failing silently.

## Inputs

- race date
- training start date
- plan length in weeks
- current week
- last completed sessions
- active constraints or injuries

## Conservative Defaults

- If yesterday's quality session was missed, do not automatically stack it onto
  today; preserve recovery spacing.
- If the athlete is returning from injury, prefer easy running or cross-training.
- If the long run is uncertain, ask the athlete or recommend the safer shorter
  option.

## Output

Always disclose that the calendar was unavailable and that the session is an
inference.
