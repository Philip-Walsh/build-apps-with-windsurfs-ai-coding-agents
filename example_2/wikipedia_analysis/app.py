from flask import Flask, render_template, request
import requests
import re
from bs4 import BeautifulSoup

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    analysis_results = None
    article_title = ""
    error_message = None
    
    if request.method == 'POST':
        article_title = request.form.get('article_title', '').strip()
        if article_title:
            try:
                analysis_results = analyze_wikipedia_article(article_title)
            except Exception as e:
                error_message = f"Error analyzing article: {str(e)}"
    
    return render_template('index.html', 
                          analysis_results=analysis_results, 
                          article_title=article_title,
                          error_message=error_message)

def analyze_wikipedia_article(title):
    # Format the title for the URL
    formatted_title = title.replace(' ', '_')
    url = f"https://en.wikipedia.org/wiki/{formatted_title}"
    
    # Get the article content
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to retrieve article. Status code: {response.status_code}")
    
    # Parse the HTML
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Extract the main content
    content_div = soup.find(id="mw-content-text")
    if not content_div:
        raise Exception("Could not find main content")
    
    # Remove references, tables, and other non-text elements
    for element in content_div.find_all(['table', 'sup', 'math', 'span.reference']):
        element.extract()
    
    # Get the text
    paragraphs = content_div.find_all('p')
    text = ' '.join([p.get_text() for p in paragraphs])
    
    # Clean the text
    text = re.sub(r'\[\d+\]', '', text)  # Remove citation numbers
    text = re.sub(r'\s+', ' ', text)     # Normalize whitespace
    
    # Basic analysis
    word_count = len(text.split())
    sentence_count = len(re.split(r'[.!?]+', text))
    avg_word_length = sum(len(word) for word in text.split()) / word_count if word_count > 0 else 0
    
    # Find most common words (excluding common stop words)
    stop_words = {'the', 'a', 'an', 'and', 'in', 'to', 'of', 'for', 'on', 'with', 'as', 'by', 'at', 'from', 'was', 'were', 'is', 'are', 'it', 's', 'or'}
    words = [word.lower() for word in re.findall(r'\b\w+\b', text) if word.lower() not in stop_words]
    word_freq = {}
    for word in words:
        word_freq[word] = word_freq.get(word, 0) + 1
    
    common_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {
        'title': title,
        'url': url,
        'word_count': word_count,
        'sentence_count': sentence_count,
        'avg_word_length': round(avg_word_length, 2),
        'common_words': common_words,
        'excerpt': text[:500] + '...' if len(text) > 500 else text
    }

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
