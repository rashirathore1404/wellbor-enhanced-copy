import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from nltk.stem import WordNetLemmatizer
from nltk import pos_tag, ne_chunk

nltk.download('punkt')
nltk.download('stopwords')
nltk.download('wordnet')
nltk.download('averaged_perceptron_tagger')
nltk.download('maxent_ne_chunker')
nltk.download('words')


text = "Rashi is studying Computer Science in India and wants to become a Software Engineer."

print("Original Text:")
print(text)

# Tokenization
tokens = word_tokenize(text)
print("\nTokens:")
print(tokens)

# Remove Stopwords
stop_words = set(stopwords.words("english"))
filtered_tokens = [word for word in tokens if word.lower() not in stop_words]

print("\nAfter Removing Stopwords:")
print(filtered_tokens)

# Stemming
stemmer = PorterStemmer()
stemmed_words = [stemmer.stem(word) for word in filtered_tokens]

print("\nAfter Stemming:")
print(stemmed_words)

#  Lemmatization
lemmatizer = WordNetLemmatizer()
lemmatized_words = [lemmatizer.lemmatize(word) for word in filtered_tokens]

print("\nAfter Lemmatization:")
print(lemmatized_words)

# POS Tagging
pos_tags = pos_tag(tokens)
print("\nPOS Tags:")
print(pos_tags)

# Named Entity Recognition
ner = ne_chunk(pos_tags)
print("\nNamed Entities:")
print(ner)
