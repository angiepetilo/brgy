/**
 * Facebook-Style Post Creation & Edit Modal Controller
 */

/* ================= Create Modal ================= */
function openCreatePostModal() {
  const modal = document.getElementById('createPostModal');
  if (modal) {
    modal.style.display = 'flex';
    const input = document.getElementById('postContentInput');
    if (input) {
      input.focus();
    }
  }
}

function closeCreatePostModal() {
  const modal = document.getElementById('createPostModal');
  if (modal) {
    modal.style.display = 'none';
  }
}

function toggleSubmitButton() {
  const input = document.getElementById('postContentInput');
  const btn = document.getElementById('btnPostSubmit');
  if (input && btn) {
    const content = input.value.trim();
    btn.disabled = content.length === 0;
  }
}

function handleImageSelection(fileInput) {
  const previewWrapper = document.getElementById('imagePreviewWrapper');
  const previewImg = document.getElementById('imagePreviewElement');
  if (fileInput && fileInput.files && fileInput.files[0]) {
    const reader = new FileReader();
    reader.onload = function(e) {
      if (previewImg && previewWrapper) {
        previewImg.src = e.target.result;
        previewWrapper.style.display = 'block';
      }
    };
    reader.readAsDataURL(fileInput.files[0]);
  }
}

function clearSelectedImage() {
  const fileInput = document.getElementById('postImageFileInput');
  const previewWrapper = document.getElementById('imagePreviewWrapper');
  const previewImg = document.getElementById('imagePreviewElement');
  if (fileInput) fileInput.value = '';
  if (previewImg) previewImg.src = '';
  if (previewWrapper) previewWrapper.style.display = 'none';
}

/* ================= Edit Modal ================= */
function openEditPostModal(postData) {
  // Support passing a DOM element with data attributes (e.g. openEditPostModal(this))
  if (postData && (postData instanceof HTMLElement || postData.dataset)) {
    const el = postData;
    postData = {
      id: el.dataset.id,
      title: el.dataset.title || '',
      content: el.dataset.content || '',
      category: el.dataset.category || '',
      imageUrl: el.dataset.imageUrl || '',
      isPinned: el.dataset.isPinned === 'true',
      actionUrl: el.dataset.actionUrl || ''
    };
  }

  // Close any open menus
  closeAllPostMenus();

  const modal = document.getElementById('editPostModal');
  if (!modal) return;

  const form = document.getElementById('editPostForm');
  const titleInput = document.getElementById('editPostTitleInput');
  const contentInput = document.getElementById('editPostContentInput');
  const categorySelect = document.getElementById('editPostCategorySelect');
  const isPinnedInput = document.getElementById('editPostIsPinned');
  const previewWrapper = document.getElementById('editImagePreviewWrapper');
  const previewImg = document.getElementById('editImagePreviewElement');
  const fileInput = document.getElementById('editPostImageFileInput');

  if (form && postData.actionUrl) {
    form.action = postData.actionUrl;
  }

  if (titleInput) titleInput.value = postData.title || '';
  if (contentInput) contentInput.value = postData.content || '';
  if (categorySelect && postData.category) {
    categorySelect.value = postData.category;
  }
  if (isPinnedInput) {
    isPinnedInput.checked = !!postData.isPinned;
    const pinLabel = isPinnedInput.closest('.icon-btn');
    if (pinLabel) {
      pinLabel.style.opacity = postData.isPinned ? '1' : '0.5';
    }
  }

  if (fileInput) fileInput.value = '';
  if (postData.imageUrl && previewWrapper && previewImg) {
    previewImg.src = postData.imageUrl;
    previewWrapper.style.display = 'block';
  } else if (previewWrapper) {
    previewWrapper.style.display = 'none';
  }

  modal.style.display = 'flex';
  if (contentInput) contentInput.focus();
}

function closeEditPostModal() {
  const modal = document.getElementById('editPostModal');
  if (modal) {
    modal.style.display = 'none';
  }
}

function handleEditImageSelection(fileInput) {
  const previewWrapper = document.getElementById('editImagePreviewWrapper');
  const previewImg = document.getElementById('editImagePreviewElement');
  if (fileInput && fileInput.files && fileInput.files[0]) {
    const reader = new FileReader();
    reader.onload = function(e) {
      if (previewImg && previewWrapper) {
        previewImg.src = e.target.result;
        previewWrapper.style.display = 'block';
      }
    };
    reader.readAsDataURL(fileInput.files[0]);
  }
}

function clearEditSelectedImage() {
  const fileInput = document.getElementById('editPostImageFileInput');
  const previewWrapper = document.getElementById('editImagePreviewWrapper');
  const previewImg = document.getElementById('editImagePreviewElement');
  const clearFlag = document.getElementById('editClearImageFlag');
  if (fileInput) fileInput.value = '';
  if (previewImg) previewImg.src = '';
  if (previewWrapper) previewWrapper.style.display = 'none';
  if (clearFlag) clearFlag.value = '1';
}

/* ================= 3-Dots Floating Menu ================= */
function togglePostMenu(event, menuId) {
  event.stopPropagation();
  const targetMenu = document.getElementById(menuId);
  const isCurrentlyOpen = targetMenu && targetMenu.classList.contains('show');

  // Close all open menus first
  closeAllPostMenus();

  if (targetMenu && !isCurrentlyOpen) {
    targetMenu.classList.add('show');
    const trigger = targetMenu.previousElementSibling;
    if (trigger) trigger.classList.add('active');
  }
}

function closeAllPostMenus() {
  document.querySelectorAll('.post-dropdown-menu.show').forEach(function(menu) {
    menu.classList.remove('show');
    const trigger = menu.previousElementSibling;
    if (trigger) trigger.classList.remove('active');
  });
}

// Global click listener to close dropdown menus
document.addEventListener('click', function(event) {
  if (!event.target.closest('.post-card-menu-container')) {
    closeAllPostMenus();
  }
});

// Escape key listener for modals and menus
document.addEventListener('keydown', function(event) {
  if (event.key === 'Escape') {
    closeCreatePostModal();
    closeEditPostModal();
    closeAllPostMenus();
  }
});
