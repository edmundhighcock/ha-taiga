/**
 * Loads www/taiga-board-card.js into a minimal DOM stub so the card can be
 * rendered and inspected under `node --test`.
 *
 * The card is a plain classic script — no imports, no exports — that ends by
 * calling customElements.define() and pushing onto window.customCards. So it
 * is evaluated with a Function wrapper that hands the class back, and the few
 * globals it touches are stubbed below.
 */

import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));

/**
 * Which copy of the card to test. Override with TAIGA_CARD_PATH to run the
 * suite against another revision — e.g. to confirm it still catches a bug:
 *   git show <rev>:www/taiga-board-card.js > /tmp/old.js
 *   TAIGA_CARD_PATH=/tmp/old.js node --test tests/js/*.test.mjs
 */
export const CARD_PATH =
  process.env.TAIGA_CARD_PATH || join(here, "..", "..", "www", "taiga-board-card.js");

class FakeShadowRoot {
  constructor() {
    this.innerHTML = "";
  }
  // The card attaches listeners after rendering; nothing here needs to fire.
  querySelectorAll() {
    return [];
  }
  querySelector() {
    return null;
  }
}

export async function loadCardClass(path = CARD_PATH) {
  globalThis.HTMLElement = class {
    attachShadow() {
      this.shadowRoot = new FakeShadowRoot();
      return this.shadowRoot;
    }
  };
  globalThis.customElements = { define() {} };
  globalThis.window = { customCards: [] };
  globalThis.document = { createElement: () => ({}) };

  const src = await readFile(path, "utf8");
  return new Function(`${src}\nreturn TaigaBoardCard;`)();
}

/**
 * The Life project's real status tables. The two are independent id
 * sequences, which is the whole point of these tests: task "New" and story
 * "Todo" are both id 1, task "Ready for test" and story "In progress" are
 * both id 3, and "In progress" occurs in both tables under different ids.
 */
const withOrder = (rows) =>
  rows.map(([id, name, is_closed], i) => ({
    id,
    name,
    is_closed,
    color: "#999999",
    order: i,
  }));

export const STATUSES = {
  user_story: withOrder([
    [1, "Todo", false],
    [2, "Time-sensitive", false],
    [3, "In progress", false],
    [4, "Awaiting confirmation", false],
    [5, "Done", true],
    [6, "Archived", true],
    [7, "Cancelled", true],
    [8, "On Hold", true],
  ]),
  task: withOrder([
    [1, "New", false],
    [2, "In progress", false],
    [3, "Ready for test", false],
    [4, "Closed", true],
    [5, "Needs Info", false],
  ]),
};

/**
 * A board holding both kinds, with the id collisions live: story 900 is
 * "Todo" (id 1) and task 800 is "New" (id 1); story 901 is "In progress"
 * (id 3) and task 802 is "Ready for test" (id 3).
 *
 * A task is marked by carrying a user_story_id key at all — task 801 has a
 * null one, which is still a task.
 */
export const ATTRIBUTES = {
  project_name: "Life",
  project_id: 1,
  statuses: STATUSES,
  epics: [{ id: 10, subject: "Trip" }],
  user_stories: [
    { id: 900, ref: 12, subject: "Clean Spa", status: "Todo", status_id: 1, version: 3, tags: [] },
    { id: 901, ref: 13, subject: "Story in progress", status: "In progress", status_id: 3, version: 2, tags: [] },
    { id: 902, ref: 14, subject: "Parked story", status: "On Hold", status_id: 8, version: 1, tags: [] },
  ],
  tasks: [
    { id: 800, ref: 23, subject: "Plan menu; buy food order", status: "New", status_id: 1, user_story_id: 900, version: 5, tags: [] },
    { id: 801, ref: 55, subject: "Plan outward journey", status: "New", status_id: 1, user_story_id: null, version: 1, tags: [] },
    { id: 802, ref: 61, subject: "Work out oxford leg", status: "Ready for test", status_id: 3, user_story_id: 900, version: 1, tags: [] },
  ],
};

/** Render the card and return its HTML. */
export function render(CardClass, config, attributes = ATTRIBUTES) {
  const card = new CardClass();
  card.setConfig({ entity: "sensor.taiga_life", ...config });
  card.hass = {
    states: { "sensor.taiga_life": { state: "5", attributes } },
  };
  return card.shadowRoot.innerHTML;
}

/**
 * Each rendered item, keyed by Taiga id, with the type the card tagged it
 * with, the status options it was offered, and the one shown as selected.
 */
export function itemsFrom(html) {
  const blocks = html.matchAll(
    /<div class="item-card" data-item-id="(\d+)" data-item-type="(\w+)">([\s\S]*?)<\/select>/g
  );
  const out = {};
  for (const [, id, type, body] of blocks) {
    out[Number(id)] = {
      type,
      options: [...body.matchAll(/<option value="([^"]+)"/g)].map((m) => m[1]),
      selected: (body.match(/<option value="([^"]+)" selected>/) ?? [])[1],
      closeGroup: [
        ...(body.match(/<optgroup label="Close">([\s\S]*?)<\/optgroup>/) ?? ["", ""])[1]
          .matchAll(/<option value="([^"]+)"/g),
      ].map((m) => m[1]),
    };
  }
  return out;
}

/** Group or column headings, as `{ name, kind, count }`. */
export function groupsFrom(html) {
  const list = [
    ...html.matchAll(
      /class="list-group-header"[^>]*>\s*([^<(]+?)\s*(?:<span class="column-kind">(\w+)<\/span>)?\s*\((\d+)\)/g
    ),
  ].map(([, name, kind, count]) => ({ name: name.trim(), kind, count: Number(count) }));

  const kanban = [
    ...html.matchAll(
      /<span class="column-title">([^<]+?)(?:<span class="column-kind">(\w+)<\/span>)?<\/span>\s*<span class="column-count">(\d+)<\/span>/g
    ),
  ].map(([, name, kind, count]) => ({ name: name.trim(), kind, count: Number(count) }));

  return list.length ? list : kanban;
}

/** The status options offered by the create-item form. */
export function addFormOptions(html) {
  const after = html.split('class="add-status"')[1] ?? "";
  const upTo = after.split("</select>")[0] ?? "";
  return [...upTo.matchAll(/<option value="([^"]+)"/g)].map((m) => m[1]);
}
