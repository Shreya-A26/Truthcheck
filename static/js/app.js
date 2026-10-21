document.addEventListener('DOMContentLoaded', () => {

  // ==========================================
  // SmoothUI: Bottom Up Letters Animation
  // Specs: Stagger 88ms, Duration 0.4s, Ease [0.18, 1, 0.32, 1]
  // Lift: y=46px -> y=0, opacity: 0 -> 1, zero blur
  // Accessible: respects prefers-reduced-motion, aria-hidden per letter, aria-label on parent
  // ==========================================
  const initBottomUpLetters = () => {
    const targets = document.querySelectorAll('.bottom-up-letters');
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    targets.forEach((el) => {
      const text = el.textContent.trim();
      if (!text) return;

      const delay = parseInt(el.getAttribute('data-delay') || '0', 10);
      const stagger = parseInt(el.getAttribute('data-stagger') || '88', 10);
      const DURATION_S = 0.4;
      const MS = 1000;
      const EASE = 'cubic-bezier(0.18, 1, 0.32, 1)';

      el.setAttribute('aria-label', text);
      el.innerHTML = '';

      const chars = Array.from(text);
      const spans = chars.map((char, index) => {
        const span = document.createElement('span');
        span.className = 'letter';
        span.setAttribute('aria-hidden', 'true');
        span.style.display = 'inline-block';
        span.style.whiteSpace = 'pre';
        span.textContent = char === ' ' ? '\u00A0' : char;

        if (prefersReduced) {
          span.style.opacity = '1';
          span.style.transform = 'translateY(0)';
          span.style.transition = 'none';
        } else {
          span.style.opacity = '0';
          span.style.transform = 'translateY(46px)';
          span.style.transition = `opacity ${DURATION_S}s ${EASE}, transform ${DURATION_S}s ${EASE}`;
          span.style.transitionDelay = `${(delay / MS) + (index * stagger / MS)}s`;
        }
        el.appendChild(span);
        return span;
      });

      if (!prefersReduced) {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            spans.forEach(span => {
              span.style.opacity = '1';
              span.style.transform = 'translateY(0)';
            });
          });
        });
      }
    });
  };

  initBottomUpLetters();

  // ==========================================
  // 1. Text Tab Character Counter & Submission
  // ==========================================
  const newsInput = document.getElementById('newsInput');
  const charCount = document.getElementById('charCount');
  if (newsInput && charCount) {
    const updateCount = () => {
      const len = newsInput.value.length;
      charCount.textContent = `${len} character${len === 1 ? '' : 's'}`;
    };
    newsInput.addEventListener('input', updateCount);
    updateCount();
  }

  const form = document.getElementById('newsCheckForm');
  const loader = document.getElementById('simpleLoader');
  const loaderStatusText = document.getElementById('loaderStatusText');
  const submitBtn = document.getElementById('checkNewsBtn');

  const setLoaderStatus = (msg) => {
    if (loaderStatusText) loaderStatusText.textContent = msg;
  };

  const showLoader = (initialMsg) => {
    if (loader) {
      if (initialMsg) setLoaderStatus(initialMsg);
      loader.style.display = 'block';
      loader.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  };

  const hideLoader = () => {
    if (loader) loader.style.display = 'none';
  };

  let isFormSubmitting = false;

  window.addEventListener('pageshow', () => {
    isFormSubmitting = false;
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.style.opacity = '1';
      submitBtn.style.cursor = 'pointer';
    }
    hideLoader();
  });

  if (form) {
    form.addEventListener('submit', (e) => {
      if (isFormSubmitting) {
        e.preventDefault();
        return;
      }
      const val = newsInput ? newsInput.value.trim() : '';
      if (!val) {
        e.preventDefault();
        showMethodAlert('Please paste news text or enter a news URL.');
        return;
      }
      if (val.length < 15 && !val.startsWith('http://') && !val.startsWith('https://')) {
        e.preventDefault();
        showMethodAlert('Please enter at least 15 characters to analyze news credibility.');
        return;
      }
      isFormSubmitting = true;
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.style.opacity = '0.7';
        submitBtn.style.cursor = 'not-allowed';
      }
      showLoader('Checking news against verified sources...');
    });
  }

  // ==========================================
  // 2. Tab Navigation
  // ==========================================
  const tabButtons = document.querySelectorAll('.input-tabs-nav .tab-btn');
  const tabPanels = document.querySelectorAll('.tab-panel');
  const methodAlert = document.getElementById('methodAlert');
  const methodAlertMessage = document.getElementById('methodAlertMessage');

  const showMethodAlert = (msg) => {
    if (methodAlert && methodAlertMessage) {
      methodAlertMessage.textContent = msg;
      methodAlert.style.display = 'block';
      methodAlert.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  };

  const clearMethodAlert = () => {
    if (methodAlert) methodAlert.style.display = 'none';
  };

  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.getAttribute('data-tab');
      clearMethodAlert();

      tabButtons.forEach(b => {
        b.classList.remove('active');
        b.setAttribute('aria-selected', 'false');
      });
      tabPanels.forEach(p => {
        p.classList.remove('active');
        p.style.display = 'none';
      });

      btn.classList.add('active');
      btn.setAttribute('aria-selected', 'true');

      const activePanel = document.getElementById(`panel-${target}`);
      if (activePanel) {
        activePanel.classList.add('active');
        activePanel.style.display = 'block';
      }
    });
  });

  // Helper: Format file sizes cleanly
  const formatBytes = (bytes) => {
    if (!bytes || bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  // Helper: Submit verified review text into existing pipeline
  const submitFinalVerification = (text, inputType, articleTitle) => {
    if (isFormSubmitting) return;
    const finalForm = document.getElementById('reviewedVerificationForm');
    const finalInput = document.getElementById('finalNewsInput');
    const finalType = document.getElementById('finalInputType');
    const finalTitle = document.getElementById('finalArticleTitle');

    if (finalForm && finalInput && finalType && finalTitle) {
      isFormSubmitting = true;
      finalInput.value = text;
      finalType.value = inputType;
      finalTitle.value = articleTitle || '';
      showLoader('Checking news against verified sources…');
      finalForm.submit();
    }
  };

  // Helper: Drag and Drop Wireup
  const setupDropzone = (dropzoneId, inputId, onFileSelected) => {
    const dropzone = document.getElementById(dropzoneId);
    const input = document.getElementById(inputId);
    if (!dropzone || !input) return;

    ['dragenter', 'dragover'].forEach(name => {
      dropzone.addEventListener(name, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add('drag-over');
      });
    });

    ['dragleave', 'drop'].forEach(name => {
      dropzone.addEventListener(name, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove('drag-over');
      });
    });

    dropzone.addEventListener('drop', (e) => {
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        input.files = e.dataTransfer.files;
        onFileSelected(input.files[0]);
      }
    });

    input.addEventListener('change', () => {
      if (input.files && input.files.length > 0) {
        onFileSelected(input.files[0]);
      }
    });
  };

  // ==========================================
  // 3. PDF Upload & Verification
  // ==========================================
  const pdfDropzone = document.getElementById('pdfDropzone');
  const pdfInput = document.getElementById('pdfFileInput');
  const pdfBrowseBtn = document.getElementById('pdfBrowseBtn');
  const pdfEmpty = document.getElementById('pdfDropzoneEmpty');
  const pdfSelected = document.getElementById('pdfDropzoneSelected');
  const pdfFileName = document.getElementById('pdfFileName');
  const pdfFileSize = document.getElementById('pdfFileSize');
  const pdfRemoveBtn = document.getElementById('pdfRemoveBtn');
  const pdfVerifyBtn = document.getElementById('pdfVerifyBtn');
  const pdfReviewBox = document.getElementById('pdfReviewBox');
  const pdfExtractedText = document.getElementById('pdfExtractedText');
  const pdfCharCount = document.getElementById('pdfCharCount');

  let selectedPdfFile = null;

  if (pdfBrowseBtn && pdfInput) {
    pdfBrowseBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      pdfInput.click();
    });
  }

  const handlePdfSelected = (file) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      showMethodAlert('Please select a valid PDF document (.pdf).');
      return;
    }
    if (file.size > 30 * 1024 * 1024) {
      showMethodAlert('The selected PDF exceeds the 30 MB limit.');
      return;
    }
    clearMethodAlert();
    selectedPdfFile = file;
    pdfFileName.textContent = file.name;
    pdfFileSize.textContent = formatBytes(file.size);
    pdfEmpty.style.display = 'none';
    pdfSelected.style.display = 'block';
    pdfVerifyBtn.disabled = false;
    pdfVerifyBtn.textContent = 'Extract & Verify PDF';
    if (pdfReviewBox) pdfReviewBox.style.display = 'none';
  };

  setupDropzone('pdfDropzone', 'pdfFileInput', handlePdfSelected);

  if (pdfRemoveBtn) {
    pdfRemoveBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      selectedPdfFile = null;
      if (pdfInput) pdfInput.value = '';
      pdfEmpty.style.display = 'block';
      pdfSelected.style.display = 'none';
      pdfVerifyBtn.disabled = true;
      pdfVerifyBtn.textContent = 'Extract & Verify PDF';
      if (pdfReviewBox) pdfReviewBox.style.display = 'none';
      clearMethodAlert();
    });
  }

  if (pdfExtractedText && pdfCharCount) {
    pdfExtractedText.addEventListener('input', () => {
      const len = pdfExtractedText.value.length;
      pdfCharCount.textContent = `${len} character${len === 1 ? '' : 's'}`;
    });
  }

  if (pdfVerifyBtn) {
    pdfVerifyBtn.addEventListener('click', async () => {
      clearMethodAlert();
      // If user already extracted and reviewed the text
      if (pdfReviewBox && pdfReviewBox.style.display === 'block') {
        const textToVerify = pdfExtractedText.value.trim();
        if (textToVerify.length < 15) {
          showMethodAlert('The extracted text is too short to verify (minimum 15 characters).');
          return;
        }
        submitFinalVerification(textToVerify, 'pdf', `Document: ${selectedPdfFile ? selectedPdfFile.name : 'PDF'}`);
        return;
      }

      if (!selectedPdfFile) {
        showMethodAlert('Please select a PDF document first.');
        return;
      }

      pdfVerifyBtn.disabled = true;
      showLoader('Uploading file…');
      setTimeout(() => setLoaderStatus('Extracting text from PDF…'), 800);

      const formData = new FormData();
      formData.append('file_type', 'pdf');
      formData.append('file', selectedPdfFile);

      try {
        const res = await fetch('/extract', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        hideLoader();

        if (!data.success) {
          pdfVerifyBtn.disabled = false;
          showMethodAlert(data.error || 'Failed to extract text from PDF.');
          return;
        }

        // Display review box
        pdfExtractedText.value = data.extracted_text;
        const len = data.extracted_text.length;
        if (pdfCharCount) pdfCharCount.textContent = `${len} character${len === 1 ? '' : 's'}`;
        pdfReviewBox.style.display = 'block';
        pdfVerifyBtn.disabled = false;
        pdfVerifyBtn.textContent = 'Verify Extracted News';
        pdfReviewBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

      } catch (err) {
        hideLoader();
        pdfVerifyBtn.disabled = false;
        showMethodAlert('A network error occurred while uploading the PDF. Please try again.');
      }
    });
  }

  // ==========================================
  // 4. Image Upload & OCR Review Verification
  // ==========================================
  const imageDropzone = document.getElementById('imageDropzone');
  const imageInput = document.getElementById('imageFileInput');
  const imageBrowseBtn = document.getElementById('imageBrowseBtn');
  const imageEmpty = document.getElementById('imageDropzoneEmpty');
  const imageSelected = document.getElementById('imageDropzoneSelected');
  const imagePreview = document.getElementById('imagePreview');
  const imageFileName = document.getElementById('imageFileName');
  const imageFileSize = document.getElementById('imageFileSize');
  const imageRemoveBtn = document.getElementById('imageRemoveBtn');
  const imageVerifyBtn = document.getElementById('imageVerifyBtn');
  const imageReviewBox = document.getElementById('imageReviewBox');
  const imageExtractedText = document.getElementById('imageExtractedText');
  const imageCharCount = document.getElementById('imageCharCount');

  let selectedImageFile = null;

  if (imageBrowseBtn && imageInput) {
    imageBrowseBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      imageInput.click();
    });
  }

  const handleImageSelected = (file) => {
    if (!file) return;
    const validExts = ['.jpg', '.jpeg', '.png', '.webp'];
    const hasValidExt = validExts.some(ext => file.name.toLowerCase().endsWith(ext));
    if (!hasValidExt) {
      showMethodAlert('Unsupported image format. Please select a JPG, JPEG, PNG, or WEBP image.');
      return;
    }
    if (file.size > 30 * 1024 * 1024) {
      showMethodAlert('The selected image exceeds the 30 MB limit.');
      return;
    }
    clearMethodAlert();
    selectedImageFile = file;
    imageFileName.textContent = file.name;
    imageFileSize.textContent = formatBytes(file.size);

    if (imagePreview) {
      imagePreview.src = URL.createObjectURL(file);
    }
    imageEmpty.style.display = 'none';
    imageSelected.style.display = 'block';
    imageVerifyBtn.disabled = false;
    imageVerifyBtn.textContent = 'Extract Text with OCR';
    if (imageReviewBox) imageReviewBox.style.display = 'none';
  };

  setupDropzone('imageDropzone', 'imageFileInput', handleImageSelected);

  if (imageRemoveBtn) {
    imageRemoveBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      selectedImageFile = null;
      if (imageInput) imageInput.value = '';
      if (imagePreview) imagePreview.src = '';
      imageEmpty.style.display = 'block';
      imageSelected.style.display = 'none';
      imageVerifyBtn.disabled = true;
      imageVerifyBtn.textContent = 'Extract Text with OCR';
      if (imageReviewBox) imageReviewBox.style.display = 'none';
      clearMethodAlert();
    });
  }

  if (imageExtractedText && imageCharCount) {
    imageExtractedText.addEventListener('input', () => {
      const len = imageExtractedText.value.length;
      imageCharCount.textContent = `${len} character${len === 1 ? '' : 's'}`;
    });
  }

  if (imageVerifyBtn) {
    imageVerifyBtn.addEventListener('click', async () => {
      clearMethodAlert();

      // If user is already on review step, proceed to verification
      if (imageReviewBox && imageReviewBox.style.display === 'block') {
        const textToVerify = imageExtractedText.value.trim();
        if (textToVerify.length < 15) {
          showMethodAlert('The extracted text is too short to verify (minimum 15 characters). Please edit or add more text.');
          return;
        }
        submitFinalVerification(textToVerify, 'image', `Image OCR: ${selectedImageFile ? selectedImageFile.name : 'Image'}`);
        return;
      }

      if (!selectedImageFile) {
        showMethodAlert('Please select an image file first.');
        return;
      }

      imageVerifyBtn.disabled = true;
      showLoader('Uploading file…');
      setTimeout(() => setLoaderStatus('Extracting text using OCR…'), 800);

      const formData = new FormData();
      formData.append('file_type', 'image');
      formData.append('file', selectedImageFile);

      try {
        const res = await fetch('/extract', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        hideLoader();

        if (!data.success) {
          imageVerifyBtn.disabled = false;
          showMethodAlert(data.error || 'No readable text could be recognized in the image.');
          return;
        }

        imageExtractedText.value = data.extracted_text;
        const len = data.extracted_text.length;
        if (imageCharCount) imageCharCount.textContent = `${len} character${len === 1 ? '' : 's'}`;
        imageReviewBox.style.display = 'block';
        imageVerifyBtn.disabled = false;
        imageVerifyBtn.textContent = 'Verify Extracted News';
        imageReviewBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

      } catch (err) {
        hideLoader();
        imageVerifyBtn.disabled = false;
        showMethodAlert('A network error occurred while uploading the image. Please try again.');
      }
    });
  }

  // ==========================================
  // 5. Learn More / Read More Toggle on Results Page
  // ==========================================
  const toggleBtn = document.getElementById('toggleReadMoreBtn');
  const readMoreDetails = document.getElementById('readMoreDetails');
  const chevron = document.getElementById('readMoreChevron');

  if (toggleBtn && readMoreDetails) {
    toggleBtn.addEventListener('click', () => {
      const isHidden = readMoreDetails.style.display === 'none';
      const label = toggleBtn.querySelector('.btn-label') || toggleBtn.querySelector('span');
      if (isHidden) {
        readMoreDetails.style.display = 'block';
        toggleBtn.setAttribute('aria-expanded', 'true');
        if (chevron) chevron.classList.add('open');
        if (label) label.textContent = 'Hide Details';
        readMoreDetails.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      } else {
        readMoreDetails.style.display = 'none';
        toggleBtn.setAttribute('aria-expanded', 'false');
        if (chevron) chevron.classList.remove('open');
        if (label) label.textContent = 'Learn More';
      }
    });
  }
});
