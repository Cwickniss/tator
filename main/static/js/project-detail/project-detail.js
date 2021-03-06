class ProjectDetail extends TatorPage {
  constructor() {
    super();

    window._uploader = new Worker("/static/js/tasks/upload-worker.js");

    const main = document.createElement("main");
    main.setAttribute("class", "d-flex");
    this._shadow.appendChild(main);

    const section = document.createElement("section");
    section.setAttribute("class", "sections-wrap py-6 px-5 col-3 text-gray");
    main.appendChild(section);

    const folderHeader = document.createElement("div");
    folderHeader.setAttribute("class", "d-flex flex-justify-between flex-items-center py-4");
    section.appendChild(folderHeader);

    const folderText = document.createElement("h2");
    folderText.setAttribute("class", "h3 text-semibold");
    folderText.textContent = "Library";
    folderHeader.appendChild(folderText);

    const addFolderButton = document.createElement("button");
    addFolderButton.setAttribute("class", "px-0 f2 btn-clear text-gray hover-text-white");
    folderHeader.appendChild(addFolderButton);

    const addFolderSpan = document.createElement("span");
    addFolderSpan.setAttribute("class", "f1 px-1");
    addFolderSpan.textContent = "+";
    addFolderButton.appendChild(addFolderSpan);

    const addFolderText = document.createTextNode("Add folder");
    addFolderButton.appendChild(addFolderText);

    this._folders = document.createElement("ul");
    this._folders.setAttribute("class", "sections");
    section.appendChild(this._folders);

    //const savedSearchesHeader = document.createElement("h2");
    //savedSearchesHeader.setAttribute("class", "py-4 h3 text-semibold");
    //savedSearchesHeader.textContent = "Saved Searches";
    //section.appendChild(savedSearchesHeader);

    //this._savedSearches = document.createElement("ul");
    //this._savedSearches.setAttribute("class", "sections");
    //section.appendChild(this._savedSearches);

    const mainSection = document.createElement("section");
    mainSection.setAttribute("class", "project__main py-3 px-6 flex-grow");
    main.appendChild(mainSection);

    const div = document.createElement("div");
    div.setAttribute("class", "py-6");
    mainSection.appendChild(div);

    const header = document.createElement("div");
    header.setAttribute("class", "main__header d-flex flex-justify-between");
    div.appendChild(header);

    const h1 = document.createElement("h1");
    h1.setAttribute("class", "h1");
    header.appendChild(h1);

    this._projectText = document.createTextNode("");
    h1.appendChild(this._projectText);

    const buttons = document.createElement("div");
    buttons.setAttribute("class", "d-flex");
    header.appendChild(buttons);

    this._algorithmButton = document.createElement("algorithm-button");
    buttons.appendChild(this._algorithmButton);

    this._activityButton = document.createElement("activity-button");
    buttons.appendChild(this._activityButton);

    this._description = document.createElement("project-text");
    div.appendChild(this._description);

    const subheader = document.createElement("div");
    subheader.setAttribute("class", "d-flex flex-justify-between");
    mainSection.appendChild(subheader);

    this._search = document.createElement("project-search");
    subheader.appendChild(this._search);

    this._collaborators = document.createElement("project-collaborators");
    subheader.appendChild(this._collaborators);

    this._projects = document.createElement("div");
    mainSection.appendChild(this._projects);

    this._mediaSection = document.createElement("media-section");
    this._projects.appendChild(this._mediaSection);

    const deleteSection = document.createElement("delete-section-form");
    this._projects.appendChild(deleteSection);

    const deleteFile = document.createElement("delete-file-form");
    this._projects.appendChild(deleteFile);

    this._modalNotify = document.createElement("modal-notify");
    this._projects.appendChild(this._modalNotify);

    const cancelJob = document.createElement("cancel-confirm");
    this._shadow.appendChild(cancelJob);

    const newSectionDialog = document.createElement("new-section-dialog");
    this._projects.appendChild(newSectionDialog);

    const uploadDialog = document.createElement("upload-dialog");
    this._projects.appendChild(uploadDialog);

    this._activityNav = document.createElement("activity-nav");
    main.appendChild(this._activityNav);

    this._leaveConfirmOk = false;

    window.addEventListener("beforeunload", evt => {
      if (this._leaveConfirmOk) {
        evt.preventDefault();
        evt.returnValue = '';
        window.alert("Uploads are in progress. Still leave?");
      }
    });

    addFolderButton.addEventListener("click", evt => {
      newSectionDialog.init("Add Folder", "folder");
      newSectionDialog.setAttribute("is-open", "");
      this.setAttribute("has-open-modal", "");
    });

    newSectionDialog.addEventListener("close", evt => {
      if (newSectionDialog._confirm) {
        let spec;
        if (newSectionDialog._sectionType == "folder") {
          spec = {name: newSectionDialog._input.value,
                  tator_user_sections: uuidv1()};
        } else if (newSectionDialog._sectionType == "savedSearch") {
          //TODO: Handle adding saved search
        } else if (newSectionDialog._sectionType == "playlist") {
          //TODO: Handle adding playlist
        }
        const projectId = Number(this.getAttribute("project-id"));
        fetch(`/rest/Sections/${projectId}`, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "X-CSRFToken": getCookie("csrftoken"),
            "Accept": "application/json",
            "Content-Type": "application/json"
          },
          body: JSON.stringify(spec),
        })
        .then(response => response.json())
        .then(section => {
          if (newSectionDialog._sectionType == "folder") {
            const card = document.createElement("section-card");
            const sectionObj = {id: section.id,
                                project: projectId,
                                name: spec.name,
                                tator_user_sections: spec.tator_user_sections};
            card.init(sectionObj, true);
            this._folders.appendChild(card);
            card.addEventListener("click", () => {
              this._selectSection(sectionObj, projectId);
              for (const child of this._folders.children) {
                child.active = false;
              }
              card.active = true;
            });
          }
        });
      }
      this.removeAttribute("has-open-modal");
    });

    this._mediaSection.addEventListener("filesadded", evt => {
      this._leaveConfirmOk = true;
      uploadDialog.setTotalFiles(evt.detail.numStarted);
      uploadDialog.setAttribute("is-open", "");
      this.setAttribute("has-open-modal", "");
    });

    uploadDialog.addEventListener("cancel", evt => {
      window._uploader.postMessage({command: "cancelUploads"});
      this.removeAttribute("has-open-modal");
    });

    uploadDialog.addEventListener("close", evt => {
      this.removeAttribute("has-open-modal");
    });

    window._uploader.addEventListener("message", evt => {
      const msg = evt.data;
      if (msg.command == "uploadProgress") {
        uploadDialog.setProgress(msg.percent, `Uploading ${msg.filename}`);
      } else if (msg.command == "uploadDone") {
        uploadDialog.uploadFinished();
      } else if (msg.command == "uploadFailed") {
        uploadDialog.addError(`Failed to upload ${msg.filename}`);
      } else if (msg.command == "allUploadsDone") {
        this._leaveConfirmOk = false;
        uploadDialog.finish();
      }
    });

    this._mediaSection.addEventListener("newName", evt => {
      for (const sectionCard of this._folders.children) {
        if (sectionCard._section) {
          if (sectionCard._section.id == evt.detail.id) {
            sectionCard.rename(evt.detail.sectionName);
          }
        }
      }
    });

    this._activityButton.addEventListener("click", () => {
      this._activityNav.open();
      this._activityNav.reload();
      this.setAttribute("has-open-modal", "");
    });

    this._activityNav.addEventListener("close", evt => {
      this.removeAttribute("has-open-modal", "");
    });

    this._activityNav.addEventListener("deleteJobs", evt => {
      cancelJob.init(evt.detail.uid, evt.detail.gid, this.getAttribute("project-id"));
      cancelJob.setAttribute("is-open", "");
    });

    this._removeCallback = evt => {
      deleteSection.init(evt.detail.projectId, evt.detail.section, evt.detail.sectionParams);
      deleteSection.setAttribute("is-open", "");
      this.setAttribute("has-open-modal", "");
    };

    deleteSection.addEventListener("close", evt => {
      this.removeAttribute("has-open-modal", "");
    });

    deleteSection.addEventListener("confirmDelete", evt => {
      for (const sectionCard of this._folders.children) {
        if (sectionCard._section) {
          if (sectionCard._section.id == evt.detail.id) {
            sectionCard.parentNode.removeChild(sectionCard);
            this._folders.children[0].click();
          }
        }
      }
      deleteSection.removeAttribute("is-open");
      this.removeAttribute("has-open-modal", "");
    });

    this._deleteFileCallback = evt => {
      deleteFile.setAttribute("media-id", evt.detail.mediaId);
      deleteFile.setAttribute("media-name", evt.detail.mediaName);
      deleteFile.setAttribute("is-open", "");
      this.setAttribute("has-open-modal", "");
    };

    deleteFile.addEventListener("close", evt => {
      this.removeAttribute("has-open-modal", "");
    });

    deleteFile.addEventListener("confirmFileDelete", evt => {
      this._mediaSection.removeMedia(evt.detail.mediaId);
      deleteFile.removeAttribute("is-open");
      this.removeAttribute("has-open-modal", "");
    });

    this._modalNotify.addEventListener("close", evt => {
      this.removeAttribute("has-open-modal", "");
    });

    this._newAlgorithmCallback = evt => {
      const newAlgorithm = document.createElement("new-algorithm-form");
      this._projects.appendChild(newAlgorithm);
      newAlgorithm.setAttribute("is-open", "");
      this.setAttribute("has-open-modal", "");
      newAlgorithm.addEventListener("close", evt => {
        this.removeAttribute("has-open-modal", "");
        this._projects.removeChild(evt.target);
      });
    };

    this._algorithmButton.addEventListener("newAlgorithm", this._newAlgorithmCallback);

    cancelJob.addEventListener("confirmGroupCancel", () => {
      cancelJob.removeAttribute("is-open");
    });

    cancelJob.addEventListener("close", () => {
      this.removeAttribute("has-open-modal");
    });

    this._loaded = 0;
    this._needScroll = true;

    this._lastQuery = (this._search.value == "" ? null : this._search.value);
    this._search.addEventListener("filterProject", evt => {
      const query = evt.detail.query;
      if (query != this._lastQuery) {
        if (query.length >= 3) {
          this._lastQuery = query;
        } else if (query == "") {
          this._lastQuery = null;
        }
        this._mediaSection.searchString = this._lastQuery;
        this._mediaSection.reload();
      }
    });
  }

  static get observedAttributes() {
    return ["project-id", "token"].concat(TatorPage.observedAttributes);
  }

  _notify(title, message, error_or_ok) {
    this._modalNotify.init(title, message, error_or_ok);
    this._modalNotify.setAttribute("is-open", "");
    this.setAttribute("has-open-modal", "");
  }

  _init() {
    const projectId = this.getAttribute("project-id");
    this._activityNav.init(projectId);
    // Get info about the project.
    const projectPromise = fetch("/rest/Project/" + projectId, {
      method: "GET",
      credentials: "same-origin",
      headers: {
        "X-CSRFToken": getCookie("csrftoken"),
        "Accept": "application/json",
        "Content-Type": "application/json"
      }
    });
    const sectionPromise = fetch("/rest/Sections/" + projectId, {
      method: "GET",
      credentials: "same-origin",
      headers: {
        "X-CSRFToken": getCookie("csrftoken"),
        "Accept": "application/json",
        "Content-Type": "application/json"
      }
    });
    const algoPromise = fetch("/rest/Algorithms/" + projectId, {
      method: "GET",
      credentials: "same-origin",
      headers: {
        "X-CSRFToken": getCookie("csrftoken"),
        "Accept": "application/json",
        "Content-Type": "application/json"
      }
    });
    Promise.all([
      projectPromise,
      sectionPromise,
      algoPromise,
    ])
    .then(([projectResponse, sectionResponse, algoResponse]) => {
      const projectData = projectResponse.json();
      const sectionData = sectionResponse.json();
      const algoData = algoResponse.json();
      Promise.all([projectData, sectionData, algoData])
      .then(([project, sections, algos]) => {
        // First hide algorithms if needed. These are not appropriate to be
        // run at the project/section/media level.
        const hiddenAlgos = ['tator_extend_track', 'tator_fill_track_gaps'];
        const parsedAlgos = algos.filter(function(alg) {
          return !hiddenAlgos.includes(alg.name);
        } );
        this._algorithms = parsedAlgos;
        this._permission = project.permission;
        this._mediaSection.permission = this._permission;
        this._mediaSection.algorithms = this._algorithms;
        if (!hasPermission(project.permission, "Can Execute")) {
          this._algorithmButton.style.display = "none";
        }
        if (!hasPermission(project.permission, "Can Transfer")) {
          //this._uploadButton.style.display = "none";
        }
        this._projectText.nodeValue = project.name;
        this._search.setAttribute("project-name", project.name);
        this._description.setAttribute("text", project.summary);
        this._collaborators.usernames = project.usernames;
        this._search.autocomplete = project.filter_autocomplete;
        let projectParams = null;
        const home = document.createElement("section-card");
        home.init(null, false);
        home.addEventListener("click", () => {
          this._selectSection(null, projectId);
          for (const child of this._folders.children) {
            child.active = false;
          }
          home.active = true;
        });
        this._folders.appendChild(home);
        for (const section of sections) {
          const hasSection = Boolean(section.tator_user_sections);
          const hasSearch = (Boolean(section.lucene_search)
                             || Boolean(section.media_bools)
                             || Boolean(section.annotation_bools));
          const isFolder = hasSection && !hasSearch;
          const card = document.createElement("section-card");
          card.init(section, isFolder);
          if (isFolder) {
            this._folders.appendChild(card);
          } else {
            //this._savedSearches.appendChild(card);
          }
          card.addEventListener("click", () => {
            this._selectSection(section, projectId);
            for (const child of this._folders.children) {
              child.active = false;
            }
            card.active = true;
          });
        }
        const params = new URLSearchParams(document.location.search.substring(1));
        if (params.has("search")) {
          this._mediaSection.searchString = params.get("search");
        }
        if (params.has("section")) {
          const sectionId = Number(params.get("section"));
          for (const child of this._folders.children) {
            if (child._section) {
              if (child._section.id == sectionId) {
                child.click();
                break;
              }
            }
          }
        } else {
          home.click();
        }
      });
    });
  }

  attributeChangedCallback(name, oldValue, newValue) {
    TatorPage.prototype.attributeChangedCallback.call(this, name, oldValue, newValue);
    switch (name) {
      case "username":
        //this._uploadButton.setAttribute("username", newValue);
        break;
      case "project-id":
        //this._uploadButton.setAttribute("project-id", newValue);
        this._algorithmButton.setAttribute("project-id", newValue);
        this._init();
        break;
      case "token":
        //this._uploadButton.setAttribute("token", newValue);
        break;
    }
  }

  _selectSection(section, projectId) {
    this._mediaSection.init(projectId, section, this.getAttribute("username"),
                            this.getAttribute("token"));
    this._mediaSection.addEventListener("remove", this._removeCallback);
    this._mediaSection.addEventListener("deleteFile", this._deleteFileCallback);
    this._mediaSection.addEventListener("newAlgorithm", this._newAlgorithmCallback);
    let params = new URLSearchParams(document.location.search.substring(1));
    params.delete("section");
    if (section !== null) {
      params.set("section", section.id);
    }
    const path = document.location.pathname;
    const searchArgs = params.toString();
    let newUrl = path;
    newUrl += "?" + searchArgs;
    let sectionName = "All Media";
    if (section !== null) {
      sectionName = section.name;
    }
    window.history.replaceState(`${this._projectText.textContent}|${sectionName}`, "Filter", newUrl);
  }
}

customElements.define("project-detail", ProjectDetail);
