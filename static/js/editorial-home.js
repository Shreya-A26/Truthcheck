/**
 * TruthLens Premium Editorial Homepage Scripts
 * Isolated subtle 3D mouse tracking, scroll-driven reveals, and anchor navigation
 */
(function() {
  'use strict';

  // Check if reduced motion is preferred
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // --------------------------------------------------------------------------
  // 1. Scroll-Driven Section Reveal (IntersectionObserver)
  // --------------------------------------------------------------------------
  function initScrollReveals() {
    const revealElements = document.querySelectorAll('.ed-reveal');
    if (!revealElements.length) return;

    if (prefersReducedMotion || !('IntersectionObserver' in window)) {
      revealElements.forEach(el => el.classList.add('is-visible'));
      return;
    }

    const observerOptions = {
      root: null,
      rootMargin: '0px 0px -8% 0px',
      threshold: 0.12
    };

    const revealObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, observerOptions);

    revealElements.forEach(el => revealObserver.observe(el));
  }

  // --------------------------------------------------------------------------
  // 2. Subtle 3D Perspective Mouse Interaction for Hero Composition
  // --------------------------------------------------------------------------
  function initHero3DTilt() {
    if (prefersReducedMotion) return;

    const stageWrap = document.querySelector('.ed-hero-stage-wrap');
    const stage = document.querySelector('.ed-hero-3d-stage');
    if (!stageWrap || !stage) return;

    let targetRotateX = 0;
    let targetRotateY = 0;
    let currentRotateX = 0;
    let currentRotateY = 0;
    let rafId = null;
    let isHovering = false;

    function onMouseMove(e) {
      const rect = stageWrap.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      const centerX = rect.width / 2;
      const centerY = rect.height / 2;

      // Restrained tilt angles (max +/- 8 degrees)
      const percentX = (x - centerX) / centerX;
      const percentY = (y - centerY) / centerY;

      targetRotateY = percentX * 7;
      targetRotateX = -percentY * 6;

      if (!isHovering) {
        isHovering = true;
        renderLoop();
      }
    }

    function onMouseLeave() {
      targetRotateX = 0;
      targetRotateY = 0;
      isHovering = false;
    }

    function renderLoop() {
      // Smooth lerp easing
      currentRotateX += (targetRotateX - currentRotateX) * 0.08;
      currentRotateY += (targetRotateY - currentRotateY) * 0.08;

      stage.style.transform = `rotateX(${currentRotateX.toFixed(2)}deg) rotateY(${currentRotateY.toFixed(2)}deg)`;

      // Continue animating until settled
      if (isHovering || Math.abs(targetRotateX - currentRotateX) > 0.05 || Math.abs(targetRotateY - currentRotateY) > 0.05) {
        rafId = requestAnimationFrame(renderLoop);
      } else {
        stage.style.transform = 'rotateX(0deg) rotateY(0deg)';
        rafId = null;
      }
    }

    stageWrap.addEventListener('mousemove', onMouseMove, { passive: true });
    stageWrap.addEventListener('mouseleave', onMouseLeave, { passive: true });
  }

  // --------------------------------------------------------------------------
  // 3. Smooth Anchor Navigation for In-Page Section Links
  // --------------------------------------------------------------------------
  function initAnchorNavigation() {
    const anchorLinks = document.querySelectorAll('a[href^="#"]');
    anchorLinks.forEach(link => {
      link.addEventListener('click', function(e) {
        const targetId = this.getAttribute('href');
        if (!targetId || targetId === '#') return;

        const targetEl = document.querySelector(targetId);
        if (targetEl) {
          e.preventDefault();
          targetEl.scrollIntoView({
            behavior: prefersReducedMotion ? 'auto' : 'smooth',
            block: 'start'
          });
        }
      });
    });
  }

  // Initialize all interactive modules once DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      initScrollReveals();
      initHero3DTilt();
      initAnchorNavigation();
    });
  } else {
    initScrollReveals();
    initHero3DTilt();
    initAnchorNavigation();
  }
})();
