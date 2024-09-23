import os
import pandas as pd
import numpy as np
import torch
from torch import nn
import joblib
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics.pairwise import cosine_similarity
from tqdm import tqdm
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import pandas as pd
import numpy as np
import torch
from torch import nn
import joblib
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics.pairwise import cosine_similarity
from tqdm import tqdm
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Check if CUDA is available
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

class NCF(nn.Module):
    def __init__(self, num_users, num_movies, embedding_size=64, layers=[ 128, 64, 32]):
        super(NCF, self).__init__()
        self.user_embedding = nn.Embedding(num_users, embedding_size)
        self.movie_embedding = nn.Embedding(num_movies, embedding_size)

        self.fc_layers = nn.ModuleList()
        input_size = embedding_size * 2
        for layer_size in layers:
            self.fc_layers.append(nn.Linear(input_size, layer_size))
            self.fc_layers.append(nn.ReLU())
            self.fc_layers.append(nn.BatchNorm1d(layer_size))
            self.fc_layers.append(nn.Dropout(0.2))
            input_size = layer_size

        self.output_layer = nn.Linear(layers[-1], 1)

    def forward(self, user_input, movie_input):
        user_embedded = self.user_embedding(user_input)
        movie_embedded = self.movie_embedding(movie_input)

        vector = torch.cat([user_embedded, movie_embedded], dim=-1)
        for layer in self.fc_layers:
            vector = layer(vector)

        output = self.output_layer(vector)
        return output.squeeze()

class MemoryEfficientSVDModel:
    def __init__(self, user_factors, movie_factors, user_encoder, movie_encoder):
        self.user_factors = user_factors
        self.movie_factors = movie_factors
        self.user_encoder = user_encoder
        self.movie_encoder = movie_encoder

    def predict(self, user, movie):
        try:
            user_idx = self.user_encoder.transform([str(user)])[0]
            movie_idx = self.movie_encoder.transform([str(movie)])[0]
            prediction = np.dot(self.user_factors[user_idx], self.movie_factors[movie_idx])
            return min(max(prediction, 0.5), 5)  # Clip prediction between 0.5 and 5
        except ValueError:
            return 2.5  # Return average rating if user or movie is not in the training set

    @classmethod
    def load(cls, path):
        user_factors = np.load(f"{path}_user_factors.npy")
        movie_factors = np.load(f"{path}_movie_factors.npy")
        user_encoder = joblib.load(f"{path}_user_encoder.joblib")
        movie_encoder = joblib.load(f"{path}_movie_encoder.joblib")
        return cls(user_factors, movie_factors, user_encoder, movie_encoder)

def load_models_and_data():
    print("Loading saved models and data...")
    
    # Load smaller data structures first
    user_encoder = joblib.load('user_encoder.joblib')
    movie_encoder = joblib.load('movie_encoder.joblib')
    
    # Load numpy arrays
    encodings = np.load('encodings.npy', mmap_mode='r')  # Memory-map the file
    
    # Load models
    ncf_model = NCF(len(user_encoder.classes_), len(movie_encoder.classes_))
    ncf_model.load_state_dict(torch.load('ncf_model.pth', map_location='cpu'))  # Load to CPU first
    ncf_model.to(device)
    ncf_model.eval()

    lgbm_model = joblib.load('lgbm_model.joblib')
    svd_model = MemoryEfficientSVDModel.load('svd_model')

    # Load DataFrames last
    df = pd.read_pickle('preprocessed_df.pkl')
    ratings_df = pd.read_pickle('ratings_df.pkl')

    return df, ratings_df, encodings, ncf_model, user_encoder, movie_encoder, lgbm_model, svd_model

def content_based_recommendations(movie_title, df, encodings, top_n=10):
    movie_title = movie_title.strip().lower()
    df['normalized_title'] = df['title'].str.strip().str.lower()

    movie_index = df[df['normalized_title'] == movie_title].index
    if len(movie_index) == 0:
        print(f"Movie '{movie_title}' not found in the dataset.")
        return []
    idx = movie_index[0]
    movie_encoding = encodings[idx].reshape(1, -1)
    cosine_sim = cosine_similarity(movie_encoding, encodings).flatten()
    sim_scores = list(enumerate(cosine_sim))
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
    sim_scores = sim_scores[1:top_n+1]
    movie_indices = [i[0] for i in sim_scores]
    return df['title'].iloc[movie_indices].tolist()

import numpy as np
import torch
from sklearn.metrics.pairwise import cosine_similarity

def generate_cf_recommendations(movie_id, df, ratings_df, svd_model, top_n=20):
    movie_id = str(movie_id)
    
    try:
        movie_idx = svd_model.movie_encoder.transform([movie_id])[0]
        movie_factor = svd_model.movie_factors[movie_idx]
        
        # Calculate similarity with all movies at once
        similarities = cosine_similarity([movie_factor], svd_model.movie_factors)[0]
        
        # Get top similar movies
        similar_indices = np.argsort(similarities)[::-1][1:top_n+1]  # Exclude the input movie
        similar_movie_ids = svd_model.movie_encoder.inverse_transform(similar_indices)
        
        recommendations = df[df['movieId'].isin(similar_movie_ids)]['title'].tolist()
        return recommendations
    except Exception as e:
        print(f"Error in CF recommendations: {str(e)}")
        return []
def generate_ncf_recommendations(movie_id, df, ncf_model, movie_encoder, top_n=20):
    ncf_model.eval()
    
    try:
        encoded_movie_id = movie_encoder.transform([movie_id])[0]
        movie_input = torch.tensor([encoded_movie_id]).to(ncf_model.movie_embedding.weight.device)
        
        with torch.no_grad():
            input_embedding = ncf_model.movie_embedding(movie_input)
            all_embeddings = ncf_model.movie_embedding.weight
            
            # Calculate cosine similarity
            similarities = torch.cosine_similarity(input_embedding, all_embeddings)
        
        # Get top similar movies
        _, top_indices = similarities.topk(top_n + 1)  # +1 to account for the input movie
        top_indices = top_indices[1:]  # Exclude the input movie
        
        top_movie_ids = movie_encoder.inverse_transform(top_indices.cpu().numpy())
        return df[df['movieId'].isin(top_movie_ids)]['title'].tolist()
    except Exception as e:
        print(f"Error in NCF recommendations: {str(e)}")
        return []

def generate_lgbm_recommendations(movie_id, df, lgbm_model, top_n=20):
    features = ['popularity', 'vote_average', 'vote_count', 'release_year', 'adult', 'status', 'original_language'] + \
               [col for col in df.columns if col.startswith('genre_')]
    
    input_movie_features = df[df['movieId'] == movie_id][features].values
    
    # Predict for all movies at once
    all_predictions = lgbm_model.predict(df[features])
    
    # Calculate similarity based on predictions
    input_prediction = lgbm_model.predict(input_movie_features)
    similarities = np.abs(all_predictions - input_prediction[0])
    
    # Get top similar movies
    similar_indices = np.argsort(similarities)[1:top_n+1]  # Exclude the input movie
    recommendations = df.iloc[similar_indices]['title'].tolist()
    
    return recommendations

def hybrid_recommendations(movie_title, df, ratings_df, encodings, ncf_model, movie_encoder, lgbm_model, svd_model, top_n=10):
    movie_title = movie_title.strip().lower()
    df['normalized_title'] = df['title'].str.strip().str.lower()

    if movie_title not in df['normalized_title'].values:
        raise ValueError(f"Movie '{movie_title}' not found in the dataset.")

    movie_id = df[df['normalized_title'] == movie_title]['movieId'].iloc[0]

    content_recs = content_based_recommendations(movie_title, df, encodings, top_n=top_n*2)
    cf_recs = generate_cf_recommendations(movie_id, df, ratings_df, svd_model, top_n=top_n*2)
    ncf_recs = generate_ncf_recommendations(movie_id, df, ncf_model, movie_encoder, top_n=top_n*2)
    lgbm_recs = generate_lgbm_recommendations(movie_id, df, lgbm_model, top_n=top_n*2)
    # Get genre and director info for the input movie
    input_movie = df[df['normalized_title'] == movie_title].iloc[0]
    input_movie_genres = set(input_movie['genres'])
    input_movie_director = input_movie['director']

    hybrid_recs = []
    content_weight = 0.3
    cf_weight = 0.2
    ncf_weight = 0.2
    lgbm_weight = 0.1
    genre_weight = 0.1
    director_weight = 0.1

    all_movies = set(content_recs + cf_recs + ncf_recs + lgbm_recs)
    hybrid_scores = {}

    for movie in all_movies:
        if movie != movie_title:
            content_score = content_weight * (1 - content_recs.index(movie) / len(content_recs)) if movie in content_recs else 0
            cf_score = cf_weight * (1 - cf_recs.index(movie) / len(cf_recs)) if movie in cf_recs else 0
            ncf_score = ncf_weight * (1 - ncf_recs.index(movie) / len(ncf_recs)) if movie in ncf_recs else 0
            lgbm_score = lgbm_weight * (1 - lgbm_recs.index(movie) / len(lgbm_recs)) if movie in lgbm_recs else 0

            # Calculate genre similarity
            movie_genres = set(df[df['title'] == movie]['genres'].iloc[0])
            genre_similarity = len(input_movie_genres.intersection(movie_genres)) / len(input_movie_genres.union(movie_genres))
            genre_score = genre_weight * genre_similarity

            # Calculate director similarity
            movie_director = df[df['title'] == movie]['director'].iloc[0]
            director_score = director_weight if input_movie_director == movie_director else 0

            # Combine scores
            hybrid_scores[movie] = content_score + cf_score + ncf_score + lgbm_score + genre_score + director_score

    sorted_recs = sorted(hybrid_scores.items(), key=lambda x: x[1], reverse=True)
    hybrid_recs = [movie for movie, score in sorted_recs[:top_n]]

    return hybrid_recs

# Load models and data
df, ratings_df, encodings, ncf_model, user_encoder, movie_encoder, lgbm_model, svd_model = load_models_and_data()


@app.route('/')
def home():
    return render_template('index.html')
@app.route('/recommend', methods=['POST'])



def recommend():
    data = request.json
    movie_title = data.get('movie_title')
    
    if not movie_title:
        return jsonify({'error': 'No movie title provided'}), 400
    
    try:
        recommendations = hybrid_recommendations(movie_title, df, ratings_df, encodings, ncf_model, movie_encoder, lgbm_model, svd_model)
        return jsonify({'recommendations': recommendations})
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': 'An unexpected error occurred'}), 500

if __name__ == '__main__':
    app.run(debug=True)