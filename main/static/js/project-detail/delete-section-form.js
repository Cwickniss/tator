class DeleteSectionForm extends ModalDialog {
  constructor() {
    super();

    const icon = document.createElement("modal-warning");
    this._header.insertBefore(icon, this._titleDiv);

    const warning = document.createElement("p");
    warning.setAttribute("class", "text-semibold py-3");
    warning.textContent = "Warning: This cannot be undone";
    this._main.appendChild(warning);

    const texts = [
      "Section files and annotations will be deleted",
      "Section shared links will be inaccessible",
    ];
    this._checks = new Array(texts.length);
    texts.forEach((item, index, array) => {
      this._checks[index] = document.createElement("labeled-checkbox");
      this._checks[index].setAttribute("text", item);
      this._main.appendChild(this._checks[index]);
    });

    this._accept = document.createElement("button");
    this._accept.setAttribute("class", "btn btn-clear btn-red");
    this._accept.setAttribute("disabled", "");
    this._accept.textContent = "Delete Section";
    this._footer.appendChild(this._accept);
    
    const cancel = document.createElement("button");
    cancel.setAttribute("class", "btn btn-clear btn-charcoal");
    cancel.textContent = "Cancel";
    this._footer.appendChild(cancel);

    cancel.addEventListener("click", this._closeCallback);

    this._checks.forEach((item, index, array) => {
      item.addEventListener("change", evt => {
        let allChecked = true;
        this._checks.forEach((item, index, array) => {
          if (!item.checked) {
            allChecked = false;
          }
        });
        if (allChecked) {
          this._accept.removeAttribute("disabled");
        } else {
          this._accept.setAttribute("disabled", "");
        }
      });
    });

    this._accept.addEventListener("click", async evt => {
      const projectId = this._project;
      const params = this._sectionParams;
      fetch(`/rest/Medias/${projectId}?${params.toString()}`, {
        method: "DELETE",
        credentials: "same-origin",
        headers: {
          "X-CSRFToken": getCookie("csrftoken"),
          "Accept": "application/json",
          "Content-Type": "application/json"
        },
      })
      .catch(err => console.log(err));
      fetch(`/rest/Section/${this._section.id}`, {
        method: "DELETE",
        credentials: "same-origin",
        headers: {
          "X-CSRFToken": getCookie("csrftoken"),
          "Accept": "application/json",
          "Content-Type": "application/json"
        },
      })
      .catch(err => console.log(err));
      this.dispatchEvent(new CustomEvent("confirmDelete", {
        detail: {id: this._section.id}
      }));
    });
  }

  init(project, section, sectionParams) {
    this._project = project;
    this._section = section;
    this._sectionParams = sectionParams;
    this._title.nodeValue = `Delete "${section.name}"`;
    this._checks.forEach((item, index, array) => {
      item.checked = false;
    });
    this._accept.setAttribute("disabled", "");
  }
}

customElements.define("delete-section-form", DeleteSectionForm);
