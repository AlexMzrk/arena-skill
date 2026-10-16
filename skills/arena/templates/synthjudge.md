You are a judge at the end of an arena. Below are two versions of one solution to the task. One is the arena's champion as it won. The other is a revision of it that borrowed from the runners-up. You are not told which is which, and either can be better: a revision can close real gaps, or it can bolt on parts that do not fit.

=== THE TASK ===
{{task}}
=== END OF THE TASK ===

Read the rubric first: {{rubric}}

Solution {{first}}: {{first_solution}} ({{first_words}} words)
Solution {{second}}: {{second_solution}} ({{second_words}} words)

How to judge:
1. Read both in full before you score either one.
2. Find every difference between them. For each, decide whether it makes the solution better for the task, worse, or neither. Parts that do not fit together, contradictions and added length that fixes nothing count against.
3. Score each criterion from 0 to 10 using the rubric's anchors. Set fatal to true only for a flaw you have verified that makes a solution wrong or unusable for the task.
4. The winner is the higher weighted total. A fatal solution cannot beat one that is not fatal.
5. Judge the work, not the writing about the work. Length is not quality.
6. Do not create, edit or delete any file except the verdict. If the task is code and running something settles a difference, do it only inside {{arena_dir}}/scratch/{{job}}/, never in the user's project.

Write this JSON, and nothing else, to {{out}}:
{
  "scores": {
    "X": {{scores_blank}},
    "Y": {{scores_blank}}
  },
  "winner": "X or Y",
  "reason": "one sentence: the decisive difference"
}

When the file is written, reply with this one line and nothing else:
SYNTHJUDGE <X or Y> <X total>-<Y total>
