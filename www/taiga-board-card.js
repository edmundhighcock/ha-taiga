/**
 * Taiga Board Card - Custom Lovelace card for Taiga project management
 *
 * Displays user stories and/or tasks in a kanban board or list view.
 * Supports changing status and creating new items.
 */

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

    const statusDefs =
      itemType === "task"
        ? attrs.statuses?.task || []
        : attrs.statuses?.user_story || [];

    // All statuses sorted (for dropdowns — lets users close items)
    const allStatuses = [...statusDefs].sort((a, b) => a.order - b.order);

    // Column statuses: only open (no "Done" column on the board)
    let columnStatuses = allStatuses.filter((s) => !s.is_closed);
    if (this._config.statuses) {
      const allowed = this._config.statuses.map((s) => s.toLowerCase());
      columnStatuses = columnStatuses.filter((s) =>
        allowed.includes(s.name.toLowerCase())
      );
    }

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
            ? this._renderKanban(items, columnStatuses, allStatuses)
            : this._renderList(items, columnStatuses, allStatuses)}
          ${this._config.show_add_form ? this._renderAddForm(columnStatuses, attrs) : ""}
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

  _renderKanban(items, columnStatuses, allStatuses) {
    const columns = columnStatuses
      .map((s) => {
        const columnItems = items.filter(
          (i) => i.status === s.name || i.status_id === s.id
        );
        return `
        <div class="kanban-column">
          <div class="column-header" style="border-top: 3px solid ${s.color}">
            <span class="column-title">${s.name}</span>
            <span class="column-count">${columnItems.length}</span>
          </div>
          <div class="column-items">
            ${columnItems.map((item) => this._renderItem(item, allStatuses)).join("")}
          </div>
        </div>`;
      })
      .join("");

    return `<div class="kanban-board">${columns}</div>`;
  }

  _renderList(items, columnStatuses, allStatuses) {
    const groups = columnStatuses
      .map((s) => {
        const groupItems = items.filter(
          (i) => i.status === s.name || i.status_id === s.id
        );
        if (groupItems.length === 0) return "";
        return `
        <div class="list-group">
          <div class="list-group-header" style="border-left: 3px solid ${s.color}">
            ${s.name} (${groupItems.length})
          </div>
          ${groupItems.map((item) => this._renderItem(item, allStatuses)).join("")}
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
      <div class="item-card" data-item-id="${item.id}" data-item-type="${item.user_story_id !== undefined ? "task" : "user_story"}">
        <div class="item-header">
          <span class="item-ref">#${item.ref}</span>
          <select class="status-select" data-item-id="${item.id}" data-item-type="${item.user_story_id !== undefined ? "task" : "user_story"}" data-version="${item.version}">
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
