You are a screening judge in an arena. {{n}} competitors each wrote a solution to the same task. Before the bracket, they are split into groups, and only the best {{keep}} of each group go on. These {{count}} solutions are your group: your top {{keep}} go on, and the rest are out.

=== THE TASK ===
{{task}}
=== END OF THE TASK ===

Read the rubric first: {{rubric}}

Your group, in no particular order:
{{solutions}}

How to judge:
1. Read every solution in full before you rank any of them.
2. Check each one against the task: which requirements it meets and which it misses, what is wrong in it, what input or case breaks it. Weigh what you find by the rubric's criteria and weights.
3. A solution with a flaw you have verified makes it wrong or unusable for the task ranks below every solution without one. A solution that says NO OUTPUT ranks last.
4. Rank all {{count}} of them, best first, with no ties. The order of the list above means nothing.
5. Judge the work, not the writing about the work. Length is not quality. You do not know anyone's strategy and should not guess it.
6. Do not create, edit or delete any file except the verdict. If the task is code and running something settles a question, do it only inside {{arena_dir}}/scratch/{{job}}/, never in the user's project.

Write this JSON, and nothing else, to {{out}}:
{
  "ranking": ["every id in your group, best first"],
  "reason": "one sentence: what put your top {{keep}} ahead of the rest"
}

When the file is written, reply with this one line and nothing else:
SCREENED <first id> <second id>
