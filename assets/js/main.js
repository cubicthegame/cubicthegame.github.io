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

// ===== Screenshot carousel =====
const track = document.querySelector('.carousel-track');
if (track){
  const prevBtn = document.querySelector('.carousel-controls .prev');
  const nextBtn = document.querySelector('.carousel-controls .next');
  const scrollAmount = () => track.querySelector('img')?.clientWidth + 16 || 300;
  prevBtn?.addEventListener('click', ()=> track.scrollBy({left:-scrollAmount(), behavior:'smooth'}));
  nextBtn?.addEventListener('click', ()=> track.scrollBy({left:scrollAmount(), behavior:'smooth'}));
}

// ===== Subscribe form (static hosting: hook up to your provider, e.g. Mailchimp/Buttondown) =====
const subForm = document.querySelector('.subscribe-form');
if (subForm){
  subForm.addEventListener('submit', (e)=>{
    e.preventDefault();
    const success = document.querySelector('.subscribe-success');
    // TODO: wire this up to a real newsletter provider endpoint.
    if (success) success.style.display = 'block';
    subForm.reset();
  });
}
