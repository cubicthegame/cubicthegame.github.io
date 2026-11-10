// ===== Navbar scroll state =====
const navbar = document.querySelector('.navbar');
const navLogo = document.querySelector('.nav-center img');
const heroLogo = document.querySelector('.hero-logo');

function onScroll(){
  if (!navbar) return;
  const y = window.scrollY;
  navbar.classList.toggle('is-scrolled', y > 8);

  if (heroLogo && navLogo){
    const rect = heroLogo.getBoundingClientRect();
    // fade the small nav logo in as the big hero logo scrolls out of view
    const threshold = window.innerHeight * 0.25;
    navLogo.classList.toggle('is-visible', rect.bottom < threshold);
  }
}
window.addEventListener('scroll', onScroll, { passive:true });
onScroll();

// Native details keeps navigation usable even without JavaScript.
const mobileNav = document.querySelector('.mobile-nav');
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && mobileNav?.open) {
    mobileNav.open = false;
    mobileNav.querySelector('summary').focus();
  }
});
document.addEventListener('click', (event) => {
  if (mobileNav?.open && !mobileNav.contains(event.target)) mobileNav.open = false;
});

// Keep original videos intact; fetch and play loops only near the viewport.
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const loopVisibility = new Map();
function updateLoop(video, visible) {
  loopVisibility.set(video, visible);
  if (!visible || reducedMotion.matches || navigator.connection?.saveData || document.hidden) {
    video.pause();
    return;
  }
  if (!video.dataset.loaded) {
    video.querySelectorAll('source[data-src]').forEach((source) => {
      source.src = source.dataset.src;
    });
    video.dataset.loaded = 'true';
    video.load();
  }
  video.play().catch(() => {}); // The poster remains if autoplay is unavailable.
}
const loops = document.querySelectorAll('.lazy-video');
if ('IntersectionObserver' in window) {
  const loopObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => updateLoop(entry.target, entry.isIntersecting));
  }, { rootMargin: '150px', threshold: 0.01 });
  loops.forEach((video) => loopObserver.observe(video));
} else {
  loops.forEach((video) => updateLoop(video, true));
}
function refreshLoops() {
  loopVisibility.forEach((visible, video) => updateLoop(video, visible));
}
reducedMotion.addEventListener('change', refreshLoops);
document.addEventListener('visibilitychange', refreshLoops);

// ===== Screenshot carousel =====
const track = document.querySelector('.carousel-track');
if (track){
  const prevBtn = document.querySelector('.carousel-controls .prev');
  const nextBtn = document.querySelector('.carousel-controls .next');
  const scrollAmount = () => track.querySelector('img')?.clientWidth + 16 || 300;
  prevBtn?.addEventListener('click', ()=> track.scrollBy({left:-scrollAmount(), behavior:'smooth'}));
  nextBtn?.addEventListener('click', ()=> track.scrollBy({left:scrollAmount(), behavior:'smooth'}));
}

const subForm = document.querySelector('.subscribe-form');
if (subForm) {
  subForm.addEventListener('submit', () => {
    const success = document.querySelector('.subscribe-success');

    if (success) {
      success.style.display = 'block';
    }
  });
}
