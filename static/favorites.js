// Favorites and Hidden Projects Management
document.addEventListener('DOMContentLoaded', function() {
  initializeFavorites();
  initializeHideButtons();
  console.log('Button handlers initialized');
});

// Get favorites from localStorage
function getFavorites() {
  const fav = localStorage.getItem('favorites');
  return fav ? JSON.parse(fav) : [];
}

// Save favorites to localStorage
function saveFavorites(favorites) {
  localStorage.setItem('favorites', JSON.stringify(favorites));
  console.log('Saved favorites:', favorites);
}

// Get hidden projects from localStorage
function getHidden() {
  const hidden = localStorage.getItem('hiddenProjects');
  return hidden ? JSON.parse(hidden) : [];
}

// Save hidden projects to localStorage
function saveHidden(hidden) {
  localStorage.setItem('hiddenProjects', JSON.stringify(hidden));
  console.log('Saved hidden:', hidden);
}

// Initialize favorite buttons
function initializeFavorites() {
  const favorites = getFavorites();
  console.log('Initializing favorites, current:', favorites);
  
  document.querySelectorAll('.card-btn.favorite-btn').forEach(btn => {
    const card = btn.closest('.card');
    if (!card) {
      console.log('No card found for button');
      return;
    }
    const projectId = card.getAttribute('data-project');
    console.log('Favorite button for project:', projectId);
    
    if (favorites.includes(projectId)) {
      btn.classList.add('active');
      console.log('Set active for:', projectId);
    }
    
    btn.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      console.log('Favorite clicked for:', projectId);
      
      const currentFavorites = getFavorites();
      const index = currentFavorites.indexOf(projectId);
      
      if (index > -1) {
        currentFavorites.splice(index, 1);
        btn.classList.remove('active');
        console.log('Removed from favorites:', projectId);
      } else {
        currentFavorites.push(projectId);
        btn.classList.add('active');
        console.log('Added to favorites:', projectId);
      }
      
      saveFavorites(currentFavorites);
    });
  });
}

// Initialize hide buttons
function initializeHideButtons() {
  const hidden = getHidden();
  console.log('Initializing hide buttons, current hidden:', hidden);
  
  document.querySelectorAll('.card-btn.hide-btn').forEach(btn => {
    const card = btn.closest('.card');
    if (!card) {
      console.log('No card found for hide button');
      return;
    }
    const projectId = card.getAttribute('data-project');
    console.log('Hide button for project:', projectId);
    
    if (hidden.includes(projectId)) {
      card.style.display = 'none';
      btn.classList.add('active');
      console.log('Hidden initially:', projectId);
    }
    
    btn.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      console.log('Hide clicked for:', projectId);
      
      const currentHidden = getHidden();
      const index = currentHidden.indexOf(projectId);
      
      if (index > -1) {
        currentHidden.splice(index, 1);
        card.style.display = '';
        btn.classList.remove('active');
        console.log('Unhidden:', projectId);
      } else {
        currentHidden.push(projectId);
        card.style.display = 'none';
        btn.classList.add('active');
        console.log('Hidden:', projectId);
      }
      
      saveHidden(currentHidden);
    });
  });
}

console.log('Favorites.js loaded successfully');
