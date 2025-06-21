import { logEvent } from "../common/api.js"
import { initBottomNav } from "../common/i18n.js";
import {
    tg,
    userId,
    initData,
    tgBackButton,
    vibrateOnClick,
    backButton,
} from "../common/telegram.js";

const stepHeaders = [
    "Выбери одну или несколько категорий",
    "Выбери один или несколько тонов",
    "Выбери период выхода фильма"
];

const steps = document.querySelectorAll(".step");
const progressSteps = document.querySelectorAll(".progress-step");
const prevStepButton = document.getElementById("prevStep");
const nextStepButton = document.getElementById("nextStep");
const stepHeader = document.getElementById("stepHeader");

let currentStep = 0;
const selectedCategories = new Set();
const selectedAtmospheres = new Set();

function toggleSelection(button, group) {
    vibrateOnClick();
    const isNotImportant = button.dataset.category === "любой" || button.dataset.atmosphere === "любой";

    if (group === "category") {
        if (isNotImportant) {
            selectedCategories.clear();
        } else {
            selectedCategories.delete("любой");
            if (selectedCategories.has(button.dataset.category)) {
                selectedCategories.delete(button.dataset.category);
            } else {
                selectedCategories.add(button.dataset.category);
            }
        }
    } else if (group === "atmosphere") {
        if (isNotImportant) {
            selectedAtmospheres.clear();
        } else {
            selectedAtmospheres.delete("любой");
            if (selectedAtmospheres.has(button.dataset.atmosphere)) {
                selectedAtmospheres.delete(button.dataset.atmosphere);
            } else {
                selectedAtmospheres.add(button.dataset.atmosphere);
            }
        }
    }

    document.querySelectorAll(`.${group}`).forEach(btn => btn.classList.remove('selected'));
    selectedCategories.forEach(cat => document.querySelector(`[data-category="${CSS.escape(cat)}"]`)?.classList.add('selected'));
    selectedAtmospheres.forEach(atm => document.querySelector(`[data-atmosphere="${CSS.escape(atm)}"]`)?.classList.add('selected'));

    if (selectedCategories.size === 0) {
        document.querySelector(`.category[data-category="любой"]`)?.classList.add('selected');
        selectedCategories.add("любой");
    }
    if (selectedAtmospheres.size === 0) {
        document.querySelector(`.atmosphere[data-atmosphere="любой"]`)?.classList.add('selected');
        selectedAtmospheres.add("любой");
    }
}

document.querySelectorAll('.category').forEach(button => {
    button.addEventListener('click', () => toggleSelection(button, "category"));
});

document.querySelectorAll('.atmosphere').forEach(button => {
    button.addEventListener('click', () => toggleSelection(button, "atmosphere"));
});

function goToStep(stepIndex) {
    vibrateOnClick();
    if (stepIndex < 0 || stepIndex >= steps.length) return;
    steps[currentStep].classList.remove("active");
    steps[currentStep].style.display = "none";
    if (stepIndex < currentStep) {
        progressSteps[currentStep].classList.remove("active");
    } else {
        progressSteps[stepIndex].classList.add("active");
    }
    steps[stepIndex].style.display = "flex";
    setTimeout(() => steps[stepIndex].classList.add("active"), 10);
    stepHeader.textContent = stepHeaders[stepIndex];
    nextStepButton.textContent = stepIndex === steps.length - 1 ? "К фильмам" : "Далее →";
    prevStepButton.style.display = stepIndex === 0 ? "none" : "block";
    currentStep = stepIndex;
}

prevStepButton.addEventListener("click", () => goToStep(currentStep - 1));
nextStepButton.addEventListener("click", () => {
    if (currentStep === steps.length - 1) {
        const years = slider.noUiSlider.get();
        sessionStorage.setItem('movieCategories', JSON.stringify([...selectedCategories]));
        sessionStorage.setItem('movieAtmospheres', JSON.stringify([...selectedAtmospheres]));
        sessionStorage.setItem('yearStart', years[0]);
        sessionStorage.setItem('yearEnd', years[1]);
        sessionStorage.setItem('movieDescription', "");
        sessionStorage.setItem('movieSearch', "");
        sessionStorage.setItem('movieSuggestion', "");
        sessionStorage.setItem('userAnswers', "");
        sessionStorage.setItem('movieSearch', "");

        window.location.href = 'matching.html';

        setTimeout(() => {
            tgBackButton.hide();
            }, 50
        );
    } else {
        goToStep(currentStep + 1);
    }
});

const slider = document.getElementById('slider');

noUiSlider.create(slider, {
    start: [1990, 2025],
    connect: true,
    range: { 'min': 1950, 'max': 2025 },
    margin: 10,
    step: 1,
    format: {
        to: value => Math.round(value),
        from: value => Number(value)
    }
});

slider.noUiSlider.on("slide", function () {
    if (tg.HapticFeedback) {
        tg.HapticFeedback.impactOccurred("light");
    } else if ("vibrate" in navigator) {
        navigator.vibrate(30);
    }
});

slider.noUiSlider.on("update", function (values) {
    document.getElementById("first").textContent = values[0];
    document.getElementById("second").textContent = values[1];
});

document.addEventListener('DOMContentLoaded', async () => {
    backButton("index.html");
    initBottomNav();
    void logEvent(userId, "open", initData);

    const defaultCategory = document.querySelector('.category[data-category="любой"]');
    const defaultAtmosphere = document.querySelector('.atmosphere[data-atmosphere="любой"]');

    if (selectedCategories.size === 0 && defaultCategory) {
        selectedCategories.add("любой");
        defaultCategory.classList.add("selected");
    }

    if (selectedAtmospheres.size === 0 && defaultAtmosphere) {
        selectedAtmospheres.add("любой");
        defaultAtmosphere.classList.add("selected");
    }

});