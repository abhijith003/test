const form = document.getElementById("tutorial-form");
const youtubeUrlInput = document.getElementById("youtube-url");
const generateButton = document.getElementById("generate-button");

const statusPanel = document.getElementById("status-panel");
const statusText = document.getElementById("status-text");

const tutorialPanel = document.getElementById("tutorial-panel");
const tutorialTitle = document.getElementById("tutorial-title");
const tutorialObjective = document.getElementById("tutorial-objective");
const tutorialMeta = document.getElementById("tutorial-meta");
const videoPlayer = document.getElementById("video-player");

const stepNav = document.getElementById("step-nav");
const stepIndexLabel = document.getElementById("step-index-label");
const stepTimestamp = document.getElementById("step-timestamp");
const stepTitle = document.getElementById("step-title");
const stepSummary = document.getElementById("step-summary");
const keyPointsList = document.getElementById("key-points-list");
const keywordList = document.getElementById("keyword-list");
const questionText = document.getElementById("question-text");
const revealAnswerBtn = document.getElementById("reveal-answer-btn");
const answerText = document.getElementById("answer-text");

const prevStepBtn = document.getElementById("prev-step-btn");
const nextStepBtn = document.getElementById("next-step-btn");
const progressFill = document.getElementById("progress-fill");
const progressText = document.getElementById("progress-text");
const glossaryList = document.getElementById("glossary-list");

let tutorial = null;
let activeStepIndex = 0;

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const url = youtubeUrlInput.value.trim();
  if (!url) {
    setStatus("Please enter a YouTube URL first.", "error");
    return;
  }

  setLoading(true);
  setStatus("Extracting transcript and building your tutorial...", "info");
  tutorialPanel.hidden = true;

  try {
    const response = await fetch("/api/tutorial", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Unable to generate tutorial.");
    }

    tutorial = payload;
    activeStepIndex = 0;
    renderTutorial();
    setStatus("Tutorial generated successfully.", "success");
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unexpected error.";
    setStatus(message, "error");
  } finally {
    setLoading(false);
  }
});

revealAnswerBtn.addEventListener("click", () => {
  const isHidden = answerText.hidden;
  answerText.hidden = !isHidden;
  revealAnswerBtn.textContent = isHidden ? "Hide Answer" : "Reveal Answer";
});

prevStepBtn.addEventListener("click", () => {
  if (!tutorial || activeStepIndex === 0) {
    return;
  }
  activeStepIndex -= 1;
  renderStep();
});

nextStepBtn.addEventListener("click", () => {
  if (!tutorial || activeStepIndex >= tutorial.steps.length - 1) {
    return;
  }
  activeStepIndex += 1;
  renderStep();
});

function setLoading(isLoading) {
  generateButton.disabled = isLoading;
  generateButton.textContent = isLoading ? "Generating..." : "Generate";
}

function setStatus(message, state) {
  statusPanel.hidden = false;
  statusPanel.dataset.state = state;
  statusText.textContent = message;
}

function renderTutorial() {
  if (!tutorial) {
    return;
  }

  tutorialPanel.hidden = false;
  tutorialTitle.textContent = tutorial.title;
  tutorialObjective.textContent = tutorial.objective;
  tutorialMeta.textContent = `${tutorial.steps.length} steps • ~${tutorial.estimated_minutes} min`;
  videoPlayer.src = `https://www.youtube.com/embed/${tutorial.video_id}`;

  renderStepNavigation();
  renderStep();
  renderGlossary();
}

function renderStepNavigation() {
  if (!tutorial) {
    return;
  }

  stepNav.innerHTML = "";
  tutorial.steps.forEach((step, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = `${index + 1}. ${step.title}`;
    if (index === activeStepIndex) {
      button.classList.add("active");
    }
    button.addEventListener("click", () => {
      activeStepIndex = index;
      renderStep();
    });
    stepNav.appendChild(button);
  });
}

function renderStep() {
  if (!tutorial) {
    return;
  }

  const step = tutorial.steps[activeStepIndex];
  const totalSteps = tutorial.steps.length;

  stepIndexLabel.textContent = `Step ${activeStepIndex + 1} of ${totalSteps}`;
  stepTimestamp.textContent = `Start @ ${step.timestamp}`;
  stepTitle.textContent = step.title;
  stepSummary.textContent = step.summary;

  questionText.textContent = step.check_yourself.question;
  answerText.textContent = step.check_yourself.answer;
  answerText.hidden = true;
  revealAnswerBtn.textContent = "Reveal Answer";

  keyPointsList.innerHTML = "";
  step.key_points.forEach((point) => {
    const item = document.createElement("li");
    item.textContent = point;
    item.addEventListener("click", () => {
      item.classList.toggle("done");
    });
    keyPointsList.appendChild(item);
  });

  keywordList.innerHTML = "";
  step.keywords.forEach((keyword) => {
    const pill = document.createElement("span");
    pill.className = "keyword-pill";
    pill.textContent = keyword;
    keywordList.appendChild(pill);
  });

  prevStepBtn.disabled = activeStepIndex === 0;
  nextStepBtn.disabled = activeStepIndex === totalSteps - 1;

  const progress = ((activeStepIndex + 1) / totalSteps) * 100;
  progressFill.style.width = `${progress}%`;
  progressText.textContent = `Progress: ${activeStepIndex + 1}/${totalSteps}`;

  renderStepNavigation();
}

function renderGlossary() {
  if (!tutorial) {
    return;
  }

  glossaryList.innerHTML = "";
  const terms = tutorial.glossary || [];

  if (!terms.length) {
    const empty = document.createElement("p");
    empty.textContent = "No glossary terms extracted for this video.";
    glossaryList.appendChild(empty);
    return;
  }

  terms.forEach((entry) => {
    const wrapper = document.createElement("article");
    wrapper.className = "glossary-item";

    const term = document.createElement("h4");
    term.textContent = entry.term;
    wrapper.appendChild(term);

    const definition = document.createElement("p");
    definition.textContent = entry.definition;
    wrapper.appendChild(definition);

    glossaryList.appendChild(wrapper);
  });
}
