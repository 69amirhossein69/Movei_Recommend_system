// use tmbd api for this
const API_KEY = '';
const BASE_URL = '';
const POSTER_BASE_URL = '';
const RECOMMENDATION_API_URL = 'http://localhost:5000/recommend';

const searchInput = document.getElementById('searchInput');
const searchButton = document.getElementById('searchButton');
const movieContainer = document.getElementById('movieContainer');
const emptyState = document.getElementById('emptyState');
const movieModal = document.getElementById('movieModal');
const movieDetails = document.getElementById('movieDetails');
const closeModal = document.getElementsByClassName('close')[0];
const loadingScreen = document.getElementById('loadingScreen');

const fetchMovieDetails = async (movieTitle) => {
    const response = await fetch(`${BASE_URL}/search/movie?api_key=${API_KEY}&query=${encodeURIComponent(movieTitle)}`);
    const data = await response.json();
    return data.results[0];
};

const fetchMovieCredits = async (movieId) => {
    const response = await fetch(`${BASE_URL}/movie/${movieId}/credits?api_key=${API_KEY}`);
    const data = await response.json();
    return data;
};

const createMovieCard = (movie, credits) => {
    const director = credits.crew.find(person => person.job === 'Director');
    const cast = credits.cast.slice(0, 3).map(actor => actor.name).join(', ');

    const movieCard = document.createElement('div');
    movieCard.className = 'movie-card';
    const posterPath = movie.poster_path ? `${POSTER_BASE_URL}${movie.poster_path}` : 'https://via.placeholder.com/500x750.png?text=No+Poster';
    movieCard.innerHTML = `
        <div class="movie-poster">
            <img src="${posterPath}" alt="${movie.title}" loading="lazy">
        </div>
        <div class="movie-info">
            <h2 class="movie-title">${movie.title}</h2>
            <div class="movie-meta">
                <span>${movie.release_date ? movie.release_date.split('-')[0] : 'N/A'}</span>
                <span>${movie.vote_average.toFixed(1)}/10</span>
            </div>
            <p class="movie-overview">${movie.overview.substring(0, 150)}${movie.overview.length > 150 ? '...' : ''}</p>
            <p class="movie-cast"><strong>Director:</strong> ${director ? director.name : 'N/A'}</p>
            <p class="movie-cast"><strong>Cast:</strong> ${cast}</p>
        </div>
    `;
    movieCard.addEventListener('click', () => showMovieDetails(movie.id));
    return movieCard;
};

const showMovieDetails = async (movieId) => {
    try {
        const response = await fetch(`${BASE_URL}/movie/${movieId}?api_key=${API_KEY}&append_to_response=credits`);
        const movie = await response.json();

        const director = movie.credits.crew.find(person => person.job === 'Director');
        const cast = movie.credits.cast.slice(0, 5).map(actor => actor.name).join(', ');

        movieDetails.innerHTML = `
            <div class="movie-details-content">
                <div class="movie-details-poster">
                    <img src="${POSTER_BASE_URL}${movie.poster_path}" alt="${movie.title}">
                </div>
                <div class="movie-details-info">
                    <h2 class="movie-details-title">${movie.title}</h2>
                    <p class="movie-details-meta">${movie.release_date.split('-')[0]} | ${movie.runtime} min | ${movie.vote_average.toFixed(1)}/10</p>
                    <p class="movie-details-overview">${movie.overview}</p>
                    <p class="movie-details-cast"><strong>Director:</strong> ${director ? director.name : 'N/A'}</p>
                    <p class="movie-details-cast"><strong>Cast:</strong> ${cast}</p>
                    <p class="movie-details-genres"><strong>Genres:</strong> ${movie.genres.map(genre => genre.name).join(', ')}</p>
                </div>
            </div>
        `;

        movieModal.style.display = 'block';
    } catch (error) {
        console.error('Error fetching movie details:', error);
        movieDetails.innerHTML = '<p>Error loading movie details. Please try again later.</p>';
    }
};

const handleSearch = async () => {
    const query = searchInput.value.trim();
    if (!query) return;
    
    searchButton.disabled = true;
    movieContainer.innerHTML = '';
    emptyState.style.display = 'none';
    loadingScreen.style.display = 'flex';
    
    try {
        const response = await fetch(RECOMMENDATION_API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ movie_title: query }),
        });
        
        if (!response.ok) {
            throw new Error('Failed to fetch recommendations');
        }
        
        const data = await response.json();
        const recommendations = data.recommendations;
        
        if (recommendations.length === 0) {
            emptyState.style.display = 'flex';
            emptyState.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="film-icon"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"></rect><line x1="7" y1="2" x2="7" y2="22"></line><line x1="17" y1="2" x2="17" y2="22"></line><line x1="2" y1="12" x2="22" y2="12"></line><line x1="2" y1="7" x2="7" y2="7"></line><line x1="2" y1="17" x2="7" y2="17"></line><line x1="17" y1="17" x2="22" y2="17"></line><line x1="17" y1="7" x2="22" y2="7"></line></svg>
                <p>No recommendations found. Try another movie!</p>
            `;
        } else {
            for (const movieTitle of recommendations) {
                const movieDetails = await fetchMovieDetails(movieTitle);
                if (movieDetails) {
                    const credits = await fetchMovieCredits(movieDetails.id);
                    const movieCard = createMovieCard(movieDetails, credits);
                    movieContainer.appendChild(movieCard);
                }
            }
        }
    } catch (error) {
        console.error('Error fetching recommendations:', error);
        emptyState.style.display = 'flex';
        emptyState.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="film-icon"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"></rect><line x1="7" y1="2" x2="7" y2="22"></line><line x1="17" y1="2" x2="17" y2="22"></line><line x1="2" y1="12" x2="22" y2="12"></line><line x1="2" y1="7" x2="7" y2="7"></line><line x1="2" y1="17" x2="7" y2="17"></line><line x1="17" y1="17" x2="22" y2="17"></line><line x1="17" y1="7" x2="22" y2="7"></line></svg>
            <p>An error occurred. Please try again later.</p>
        `;
    } finally {
        searchButton.disabled = false;
        loadingScreen.style.display = 'none';
    }
};
        searchButton.addEventListener('click', handleSearch);
        searchInput.addEventListener('keypress', (event) => {
            if (event.key === 'Enter') {
                handleSearch();
            }
        });

        closeModal.onclick = function() {
            movieModal.style.display = "none";
        }

        window.onclick = function(event) {
            if (event.target == movieModal) {
                movieModal.style.display = "none";
            }
        }