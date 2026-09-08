/**
 * Regression tests for the board card's status handling.
 *
 * Taiga keeps a separate status table per object type, and the two are
 * independent id sequences whose values collide. The card once resolved a
 * single table from its card-level item_type config and applied it to every
 * row, which under `item_type: both` produced three faults at once:
 *
 *   1. a task's dropdown offered user-story statuses, so any change sent a
 *      name change_status could not resolve against task_statuses;
 *   2. no option matched the task's real status, so none was marked selected
 *      and the browser displayed the first — every task read "Todo" while
 *      actually being "New";
 *   3. grouping matched status_id across the two tables, filing tasks under
 *      whichever user-story status shared their number.
 *
 * Each numbered fault has a test below. They pass only while statuses are
 * resolved per item kind.
 */

import test from "node:test";
import assert from "node:assert/strict";

import {
  loadCardClass,
  render,
  itemsFrom,
  groupsFrom,
  addFormOptions,
} from "./card-harness.mjs";

const TASK_STATUSES = ["New", "In progress", "Ready for test", "Closed", "Needs Info"];
const STORY_STATUSES = [
  "Todo", "Time-sensitive", "In progress", "Awaiting confirmation",
  "Done", "Archived", "Cancelled", "On Hold",
];

const CardClass = await loadCardClass();
const both = { item_type: "both", view_mode: "list" };

test("fault 1: a task is offered its own statuses, never a user story's", () => {
  const items = itemsFrom(render(CardClass, both));

  assert.deepEqual(items[801].options.sort(), [...TASK_STATUSES].sort());
  // The exact status Edmund's error came from.
  assert.ok(!items[801].options.includes("Cancelled"));
  assert.ok(!items[801].options.includes("Todo"));
});

test("fault 1: a user story is offered its own statuses, never a task's", () => {
  const items = itemsFrom(render(CardClass, both));

  assert.deepEqual(items[900].options.sort(), [...STORY_STATUSES].sort());
  assert.ok(!items[900].options.includes("New"));
  assert.ok(!items[900].options.includes("Needs Info"));
});

test("each row is tagged with its own type, not the card's", () => {
  const items = itemsFrom(render(CardClass, both));

  assert.equal(items[800].type, "task");
  // A task whose user_story_id is null is still a task.
  assert.equal(items[801].type, "task");
  assert.equal(items[900].type, "user_story");
});

test("fault 2: the displayed status is the item's real one", () => {
  const items = itemsFrom(render(CardClass, both));

  // Before the fix these were undefined, and the browser showed the first
  // option instead — every task read "Todo" while being "New".
  assert.equal(items[800].selected, "New");
  assert.equal(items[801].selected, "New");
  assert.equal(items[802].selected, "Ready for test");
  assert.equal(items[900].selected, "Todo");
  assert.equal(items[901].selected, "In progress");
});

test("fault 3: grouping does not match ids across the two tables", () => {
  const groups = groupsFrom(render(CardClass, both));
  const find = (name, kind) => groups.find((g) => g.name === name && g.kind === kind);

  // Task "New" and story "Todo" are both id 1. They must not merge.
  assert.equal(find("Todo", "stories").count, 1);
  assert.equal(find("New", "tasks").count, 2);

  // Task "Ready for test" and story "In progress" are both id 3.
  assert.equal(find("Ready for test", "tasks").count, 1);
  assert.equal(find("In progress", "stories").count, 1);

  // No task landed in a story group or vice versa.
  const total = groups.reduce((n, g) => n + g.count, 0);
  assert.equal(total, 5, "one row per open item, counted once");
});

test("a status name occurring in both tables yields two distinct groups", () => {
  // "In progress" is a real name in both. With only stories on the board
  // there is one such group; the task-side one appears only when tasks do.
  const storiesOnly = groupsFrom(render(CardClass, { item_type: "user_story", view_mode: "list" }));
  assert.equal(storiesOnly.filter((g) => g.name === "In progress").length, 1);

  const mixed = groupsFrom(render(CardClass, both));
  const inProgress = mixed.filter((g) => g.name === "In progress");
  assert.equal(inProgress.length, 1, "only the story one has members here");
  assert.equal(inProgress[0].kind, "stories");
});

test("group headings are labelled by kind only when both kinds share a board", () => {
  for (const kind of ["user_story", "task"]) {
    const groups = groupsFrom(render(CardClass, { item_type: kind, view_mode: "list" }));
    assert.ok(groups.length > 0);
    assert.ok(
      groups.every((g) => g.kind === undefined),
      `single-kind board (${kind}) should not label its groups`
    );
  }

  const mixed = groupsFrom(render(CardClass, both));
  assert.ok(mixed.every((g) => g.kind !== undefined));
});

test("closed statuses stay in the Close group, per type", () => {
  const items = itemsFrom(render(CardClass, both));

  assert.deepEqual(items[900].closeGroup, ["Done", "Archived", "Cancelled", "On Hold"]);
  assert.deepEqual(items[801].closeGroup, ["Closed"]);
});

test("a closed item still displays its own status", () => {
  // "On Hold" is is_closed, so it heads no column, but story 902 sits in it
  // and its dropdown must still show it as selected.
  const items = itemsFrom(render(CardClass, both));
  assert.equal(items[902], undefined, "closed items head no open group");

  const withOnHold = groupsFrom(render(CardClass, both)).map((g) => g.name);
  assert.ok(!withOnHold.includes("On Hold"), "closed statuses are not columns");
});

test("the add form offers the statuses of the kind it creates", () => {
  // In 'both' and 'user_story' modes the form creates a user story.
  for (const item_type of ["both", "user_story"]) {
    const opts = addFormOptions(render(CardClass, { item_type, view_mode: "list" }));
    assert.ok(opts.includes("Todo"), item_type);
    assert.ok(!opts.includes("New"), item_type);
  }

  const taskOpts = addFormOptions(render(CardClass, { item_type: "task", view_mode: "list" }));
  assert.ok(taskOpts.includes("New"));
  assert.ok(!taskOpts.includes("Todo"));
});

test("kanban view resolves statuses per type just as list view does", () => {
  const html = render(CardClass, { item_type: "both", view_mode: "kanban" });
  const items = itemsFrom(html);

  assert.deepEqual(items[801].options.sort(), [...TASK_STATUSES].sort());
  assert.equal(items[801].selected, "New");
  assert.deepEqual(items[900].options.sort(), [...STORY_STATUSES].sort());

  const columns = groupsFrom(html);
  assert.equal(columns.find((c) => c.name === "New" && c.kind === "tasks").count, 2);
  assert.equal(columns.find((c) => c.name === "Todo" && c.kind === "stories").count, 1);
});

test("the statuses config filter applies within each type", () => {
  const html = render(CardClass, {
    item_type: "both",
    view_mode: "list",
    statuses: ["Todo", "New"],
  });
  const groups = groupsFrom(html);

  assert.deepEqual(
    groups.map((g) => `${g.name}/${g.kind}`).sort(),
    ["New/tasks", "Todo/stories"]
  );
});
