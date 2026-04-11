// Глобальные переменные для управления загрузкой
let progressBar = null;
let progressContainer = null;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function () {
    progressBar = document.getElementById('progressBar');
    progressContainer = document.getElementById('progressContainer');
    animateCards();
    initScrollEffects();
});

// Показать/скрыть загрузку
function showLoading(message = 'Загрузка...') {
    const loadingElements = document.querySelectorAll('.loading');
    loadingElements.forEach((el) => {
        el.classList.add('show');
        const messageEl = el.querySelector('p');
        if (messageEl) messageEl.textContent = message;
    });

    // Показать прогресс-бар
    if (progressContainer) {
        progressContainer.style.display = 'block';
        updateProgress(10);
    }
}

function hideLoading() {
    document.querySelectorAll('.loading').forEach((el) => el.classList.remove('show'));

    // Скрыть прогресс-бар
    if (progressContainer) {
        updateProgress(100);
        setTimeout(() => {
            progressContainer.style.display = 'none';
            updateProgress(0);
        }, 500);
    }
}

// Обновление прогресс-бара
function updateProgress(percent) {
    if (progressBar) {
        progressBar.style.width = percent + '%';
    }
}

// Установка прогресса для этапов
function setProgressStep(step, totalSteps) {
    const percent = (step / totalSteps) * 100;
    updateProgress(percent);
}

// Анимация появления карточек
function animateCards() {
    const cards = document.querySelectorAll('.supplier-card, .feature-card');
    cards.forEach((card, index) => {
        card.classList.add('fade-in');
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
    });
}

// Эффекты прокрутки
function initScrollEffects() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px',
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    document.querySelectorAll('.fade-in').forEach((el) => {
        observer.observe(el);
    });
}

// Плавная прокрутка для якорных ссылок
document.addEventListener('click', function (e) {
    if (e.target.matches('a[href^="#"]')) {
        e.preventDefault();
        const target = document.querySelector(e.target.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start',
            });
        }
    }
});

// Уведомления
function showToast(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `alert alert-${getAlertClass(type)} position-fixed`;
    toast.style.cssText = `
                top: 20px;
                right: 20px;
                z-index: 9999;
                min-width: 300px;
                box-shadow: var(--shadow-strong);
                border: none;
                border-radius: var(--border-radius);
                backdrop-filter: blur(10px);
            `;
    toast.innerHTML = `
                <div class="d-flex align-items-center">
                    <i class="fas ${getIconClass(type)} me-2"></i>
                    <span>${message}</span>
                </div>
            `;

    document.body.appendChild(toast);

    // Анимация появления
    setTimeout(() => (toast.style.transform = 'translateX(0)'), 10);

    // Автоматическое скрытие
    setTimeout(() => {
        toast.style.transform = 'translateX(100%)';
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

function getAlertClass(type) {
    const classes = {
        success: 'success',
        error: 'danger',
        warning: 'warning',
        info: 'info',
    };
    return classes[type] || 'info';
}

function getIconClass(type) {
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-triangle',
        warning: 'fa-exclamation-circle',
        info: 'fa-info-circle',
    };
    return icons[type] || 'fa-info-circle';
}

// Обработка ошибок
window.addEventListener('error', function (e) {
    console.error('JavaScript error:', e.error);
    showToast('Произошла ошибка. Попробуйте еще раз.', 'error');
});

window.addEventListener('unhandledrejection', function (e) {
    console.error('Unhandled promise rejection:', e.reason);
    showToast('Произошла ошибка сети. Проверьте подключение.', 'error');
});

// Navbar: синхронизация aria-expanded с Bootstrap collapse
document.addEventListener('DOMContentLoaded', function () {
    var collapseEl = document.getElementById('navbarNav');
    var toggler = document.querySelector('.navbar-toggler[data-bs-target="#navbarNav"]');
    if (!collapseEl || !toggler) return;
    collapseEl.addEventListener('shown.bs.collapse', function () {
        toggler.setAttribute('aria-expanded', 'true');
        toggler.setAttribute('aria-label', 'Закрыть меню');
    });
    collapseEl.addEventListener('hidden.bs.collapse', function () {
        toggler.setAttribute('aria-expanded', 'false');
        toggler.setAttribute('aria-label', 'Открыть меню');
    });
});
