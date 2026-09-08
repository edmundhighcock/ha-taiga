/**
 * Taiga Board Card - Custom Lovelace card for Taiga project management
 *
 * Displays user stories and/or tasks in a kanban board or list view.
 * Supports changing status and creating new items.
 */

/**
 * An item's own type, independent of the card's item_type config.
 * The sensor gives every task a user_story_id key (null when the task
 * hangs off no story); user stories never carry one.
 */
const itemKind = (item) =>
  item.user_story_id !== undefined ? "task" : "user_story";

class TaigaBoardCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("You need to define an entity");
    }
    this._config = {
      item_type: "user_story",
      view_mode: "auto",
      show_tags: true,
      show_assignee: true,
      show_epic: true,
      show_add_form: true,
      epic_filter: null,
      ...config,
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass || !this._config) return;

    const state = this._hass.states[this._config.entity];
    if (!state) {
      this.shadowRoot.innerHTML = `
        <ha-card header="Taiga">
          <div class="card-content">Entity not found: ${this._config.entity}</div>
        </ha-card>`;
      return;
    }

    const attrs = state.attributes;
    const itemType = this._config.item_type;
    let items =
      itemType === "task"
        ? attrs.tasks || []
        : itemType === "both"
          ? [...(attrs.user_stories || []), ...(attrs.tasks || [])]
          : attrs.user_stories || [];

    // Filter by epic if configured
    if (this._config.epic_filter) {
      const filter = this._config.epic_filter;
      items = items.filter((i) => {
        if (!i.epic) return false;
        if (typeof filter === "number" || /^\d+$/.test(filter)) {
          return i.epic_id === parseInt(filter);
        }
        return i.epic.toLowerCase().includes(filter.toLowerCase());
      });
    }

    // Statuses in Taiga are per-project AND per-object-type: a task's
    // status table is not a user story's, and their ids overlap (task
    // "New" and story "Todo" are both id 1). So resolve a table per item
    // KIND — never one table for the whole card, or a task is offered
    // statuses it cannot take and displays one it does not have.
    const sortByOrder = (defs) =>
      [...(defs || [])].sort((a, b) => a.order - b.order);
    const allStatusesByKind = {
      user_story: sortByOrder(attrs.statuses?.user_story),
      task: sortByOrder(attrs.statuses?.task),
    };

    const kinds =
      itemType === "task"
        ? ["task"]
        : itemType === "both"
          ? ["user_story", "task"]
          : ["user_story"];

    // Columns: open statuses only (no "Done" column on the board), each
    // tagged with the kind it belongs to so grouping never crosses tables.
    const allowed = this._config.statuses
      ? this._config.statuses.map((s) => s.toLowerCase())
      : null;
    const columns = kinds.flatMap((kind) =>
      allStatusesByKind[kind]
        .filter((s) => !s.is_closed)
        .filter((s) => !allowed || allowed.includes(s.name.toLowerCase()))
        .map((status) => ({ kind, status }))
    );

    // Both kinds on one board means duplicate names ("In progress" exists
    // in both tables), so label the group with its kind in that case only.
    const labelKind = kinds.length > 1;

    // The add form creates a user story unless the card is task-only.
    const addKind = itemType === "task" ? "task" : "user_story";
    const addStatuses = columns
      .filter((c) => c.kind === addKind)
      .map((c) => c.status);

    // Determine view mode
    const viewMode = this._resolveViewMode();

    const title = this._config.title || attrs.project_name || "Taiga";

    this.shadowRoot.innerHTML = `
      <style>${this._styles()}</style>
      <ha-card>
        <div class="card-header">
          <span class="title">${title}</span>
          <span class="badge">${state.state} open</span>
        </div>
        <div class="card-content">
          ${viewMode === "kanban"
            ? this._renderKanban(items, columns, allStatusesByKind, labelKind)
            : this._renderList(items, columns, allStatusesByKind, labelKind)}
          ${this._config.show_add_form ? this._renderAddForm(addStatuses, attrs) : ""}
        </div>
      </ha-card>`;

    this._attachEventListeners();
  }

  _resolveViewMode() {
    if (this._config.view_mode === "kanban") return "kanban";
    if (this._config.view_mode === "list") return "list";
    // auto: kanban on wide screens, list on narrow
    return this.offsetWidth > 600 ? "kanban" : "list";
  }

  _renderKanban(items, columns, allStatusesByKind, labelKind) {
    const rendered = columns
      .map(({ kind, status: s }) => {
        const columnItems = items.filter(
          (i) =>
            itemKind(i) === kind &&
            (i.status === s.name || i.status_id === s.id)
        );
        const suffix = labelKind
          ? `<span class="column-kind">${kind === "task" ? "tasks" : "stories"}</span>`
          : "";
        return `
        <div class="kanban-column">
          <div class="column-header" style="border-top: 3px solid ${s.color}">
            <span class="column-title">${s.name}${suffix}</span>
            <span class="column-count">${columnItems.length}</span>
          </div>
          <div class="column-items">
            ${columnItems
              .map((item) =>
                this._renderItem(item, allStatusesByKind[itemKind(item)])
              )
              .join("")}
          </div>
        </div>`;
      })
      .join("");

    return `<div class="kanban-board">${rendered}</div>`;
  }

  _renderList(items, columns, allStatusesByKind, labelKind) {
    const groups = columns
      .map(({ kind, status: s }) => {
        const groupItems = items.filter(
          (i) =>
            itemKind(i) === kind &&
            (i.status === s.name || i.status_id === s.id)
        );
        if (groupItems.length === 0) return "";
        const suffix = labelKind
          ? `<span class="column-kind">${kind === "task" ? "tasks" : "stories"}</span>`
          : "";
        return `
        <div class="list-group">
          <div class="list-group-header" style="border-left: 3px solid ${s.color}">
            ${s.name}${suffix} (${groupItems.length})
          </div>
          ${groupItems
            .map((item) =>
              this._renderItem(item, allStatusesByKind[itemKind(item)])
            )
            .join("")}
        </div>`;
      })
      .join("");

    return `<div class="list-view">${groups}</div>`;
  }

  _renderItem(item, statuses) {
    const tags =
      this._config.show_tags && item.tags?.length
        ? `<div class="item-tags">${item.tags.map((t) => `<span class="tag">${t}</span>`).join("")}</div>`
        : "";

    const assignee =
      this._config.show_assignee && item.assigned_to
        ? `<span class="assignee">@${item.assigned_to}</span>`
        : "";

    const epic =
      this._config.show_epic && item.epic
        ? `<span class="epic">${item.epic}</span>`
        : "";

    const openStatuses = statuses.filter((s) => !s.is_closed);
    const closedStatuses = statuses.filter((s) => s.is_closed);
    const openOptions = openStatuses
      .map(
        (s) =>
          `<option value="${s.name}" ${s.name === item.status ? "selected" : ""}>${s.name}</option>`
      )
      .join("");
    const closedOptions = closedStatuses.length
      ? `<optgroup label="Close">${closedStatuses
          .map(
            (s) =>
              `<option value="${s.name}" ${s.name === item.status ? "selected" : ""}>${s.name}</option>`
          )
          .join("")}</optgroup>`
      : "";
    const statusOptions = openOptions + closedOptions;

    return `
      <div class="item-card" data-item-id="${item.id}" data-item-type="${itemKind(item)}">
        <div class="item-header">
          <span class="item-ref">#${item.ref}</span>
          <select class="status-select" data-item-id="${item.id}" data-item-type="${itemKind(item)}" data-version="${item.version}">
            ${statusOptions}
          </select>
        </div>
        <div class="item-subject">${item.subject}</div>
        <div class="item-meta">
          ${epic}${assignee}
        </div>
        ${tags}
      </div>`;
  }

  _renderAddForm(statuses, attrs) {
    const epics = attrs.epics || [];
    const statusOptions = statuses
      .map((s) => `<option value="${s.name}">${s.name}</option>`)
      .join("");
    const epicOptions = epics.length
      ? `<select class="add-epic">
           <option value="">No epic</option>
           ${epics.map((e) => `<option value="${e.id}">${e.subject}</option>`).join("")}
         </select>`
      : "";

    return `
      <div class="add-form">
        <details>
          <summary>+ Add item</summary>
          <div class="add-form-fields">
            <input type="text" class="add-subject" placeholder="Subject" />
            <select class="add-status">${statusOptions}</select>
            ${epicOptions}
            <button class="add-button">Create</button>
          </div>
        </details>
      </div>`;
  }

  _attachEventListeners() {
    // Status change dropdowns
    this.shadowRoot.querySelectorAll(".status-select").forEach((select) => {
      select.addEventListener("change", (e) => {
        const itemId = parseInt(e.target.dataset.itemId);
        const itemType = e.target.dataset.itemType;
        const statusName = e.target.value;

        this._hass.callService("taiga", "change_status", {
          item_type: itemType,
          item_id: itemId,
          status_name: statusName,
        });
      });
    });

    // Add item button
    const addBtn = this.shadowRoot.querySelector(".add-button");
    if (addBtn) {
      addBtn.addEventListener("click", () => {
        const subject = this.shadowRoot.querySelector(".add-subject").value;
        if (!subject.trim()) return;

        const attrs = this._hass.states[this._config.entity]?.attributes;
        const statusName = this.shadowRoot.querySelector(".add-status").value;
        const epicSelect = this.shadowRoot.querySelector(".add-epic");
        const epicId = epicSelect ? epicSelect.value : null;

        const serviceData = {
          project_id: attrs?.project_id,
          subject: subject.trim(),
          status_name: statusName,
        };

        if (epicId) {
          serviceData.epic_id = parseInt(epicId);
        }

        const itemType = this._config.item_type === "task" ? "task" : "user_story";
        const service =
          itemType === "task" ? "create_task" : "create_user_story";

        this._hass.callService("taiga", service, serviceData);

        // Clear form
        this.shadowRoot.querySelector(".add-subject").value = "";
      });
    }
  }

  _styles() {
    return `
      :host {
        --card-bg: var(--ha-card-background, var(--card-background-color, #fff));
        --text-primary: var(--primary-text-color, #333);
        --text-secondary: var(--secondary-text-color, #666);
        --border: var(--divider-color, #e0e0e0);
        --accent: var(--primary-color, #03a9f4);
      }

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px 16px 0;
      }

      .title {
        font-size: 1.2em;
        font-weight: 500;
        color: var(--text-primary);
      }

      .badge {
        font-size: 0.85em;
        padding: 2px 8px;
        border-radius: 12px;
        background: var(--accent);
        color: #fff;
      }

      .card-content {
        padding: 16px;
      }

      /* Kanban */
      .kanban-board {
        display: grid;
        grid-auto-columns: minmax(160px, 1fr);
        grid-auto-flow: column;
        gap: 8px;
        overflow-x: auto;
        padding-bottom: 8px;
      }

      .kanban-column {
        min-width: 160px;
      }

      .column-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px;
        margin-bottom: 8px;
        background: var(--secondary-background-color, #f5f5f5);
        border-radius: 4px;
      }

      .column-title {
        font-weight: 500;
        font-size: 0.9em;
      }

      .column-count {
        font-size: 0.8em;
        color: var(--text-secondary);
        background: var(--card-bg);
        padding: 1px 6px;
        border-radius: 10px;
      }

      /* List */
      .list-group-header {
        font-weight: 500;
        font-size: 0.9em;
        padding: 6px 10px;
        margin: 8px 0 4px;
        background: var(--secondary-background-color, #f5f5f5);
        border-radius: 4px;
      }

      /* Only rendered when stories and tasks share one board, where the
         same status name can occur in both tables. */
      .column-kind {
        margin-left: 6px;
        font-weight: 400;
        font-size: 0.85em;
        opacity: 0.6;
      }

      /* Item cards */
      .item-card {
        padding: 8px;
        margin-bottom: 6px;
        border: 1px solid var(--border);
        border-radius: 6px;
        background: var(--card-bg);
        font-size: 0.85em;
      }

      .item-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 4px;
      }

      .item-ref {
        font-size: 0.8em;
        color: var(--text-secondary);
        font-weight: 500;
      }

      .status-select {
        font-size: 0.75em;
        padding: 1px 4px;
        border: 1px solid var(--border);
        border-radius: 4px;
        background: var(--card-bg);
        color: var(--text-primary);
        cursor: pointer;
      }

      .item-subject {
        font-weight: 500;
        margin-bottom: 4px;
        line-height: 1.3;
      }

      .item-meta {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        font-size: 0.8em;
        color: var(--text-secondary);
      }

      .epic {
        padding: 1px 6px;
        border-radius: 3px;
        background: var(--accent);
        color: #fff;
        font-size: 0.85em;
      }

      .assignee {
        font-style: italic;
      }

      .item-tags {
        display: flex;
        gap: 4px;
        flex-wrap: wrap;
        margin-top: 4px;
      }

      .tag {
        font-size: 0.75em;
        padding: 1px 6px;
        border-radius: 3px;
        background: var(--secondary-background-color, #eee);
        color: var(--text-secondary);
      }

      /* Add form */
      .add-form {
        margin-top: 12px;
        border-top: 1px solid var(--border);
        padding-top: 8px;
      }

      .add-form summary {
        cursor: pointer;
        color: var(--accent);
        font-weight: 500;
        font-size: 0.9em;
      }

      .add-form-fields {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 8px;
        align-items: center;
      }

      .add-subject {
        flex: 1;
        min-width: 150px;
        padding: 6px 8px;
        border: 1px solid var(--border);
        border-radius: 4px;
        background: var(--card-bg);
        color: var(--text-primary);
        font-size: 0.9em;
      }

      .add-status, .add-epic {
        padding: 6px 8px;
        border: 1px solid var(--border);
        border-radius: 4px;
        background: var(--card-bg);
        color: var(--text-primary);
        font-size: 0.9em;
      }

      .add-button {
        padding: 6px 16px;
        border: none;
        border-radius: 4px;
        background: var(--accent);
        color: #fff;
        cursor: pointer;
        font-size: 0.9em;
        font-weight: 500;
      }

      .add-button:hover {
        opacity: 0.9;
      }

      /* Responsive: list on narrow screens */
      @media (max-width: 600px) {
        .kanban-board {
          display: block;
        }

        .kanban-column {
          margin-bottom: 12px;
        }
      }
    `;
  }

  getCardSize() {
    return 4;
  }

  static getConfigElement() {
    return document.createElement("taiga-board-card-editor");
  }

  static getStubConfig() {
    return {
      entity: "",
      item_type: "user_story",
      view_mode: "auto",
    };
  }
}

customElements.define("taiga-board-card", TaigaBoardCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taiga-board-card",
  name: "Taiga Board",
  description: "Kanban board for Taiga project management",
});
