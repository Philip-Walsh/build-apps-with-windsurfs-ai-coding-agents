from flask import Flask, render_template, request, jsonify
import requests
import re
from bs4 import BeautifulSoup
from collections import Counter
import json

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


@app.route('/category/<category_name>', methods=['GET'])
def analyze_category(category_name):
    try:
        category_articles = get_category_articles(category_name)
        
        if not category_articles:
            return render_template('category.html',
                              category_name=category_name,
                              cumulative_freq=[],
                              articles=[],
                              error_message="No articles found in this category.")
        
        all_words = []
        
        for article in category_articles[:10]:  # Limit to 10 articles to avoid overloading
            try:
                article_analysis = analyze_wikipedia_article(article)
                # Extract words and their frequencies
                for word, count in article_analysis['word_freq'].items():
                    all_words.extend([word] * count)
            except Exception as e:
                print(f"Error analyzing article {article}: {str(e)}")
                continue
        
        # Check if we have any words to analyze
        if not all_words:
            return render_template('category.html',
                              category_name=category_name,
                              cumulative_freq=[],
                              articles=category_articles[:20],
                              error_message="Could not extract word data from articles in this category.")
        
        # Calculate cumulative frequency
        word_counts = Counter(all_words)
        total_words = len(all_words)
        
        # Sort by frequency
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Calculate cumulative frequency
        cumulative_freq = []
        running_sum = 0
        
        for word, count in sorted_words:
            freq = count / total_words
            running_sum += freq
            cumulative_freq.append({
                'word': word,
                'count': count,
                'frequency': freq,
                'cumulative_frequency': running_sum
            })
        
        return render_template('category.html',
                              category_name=category_name,
                              cumulative_freq=cumulative_freq[:100],  # Top 100 words
                              articles=category_articles[:20])  # Show up to 20 articles
    
    except Exception as e:
        return render_template('category.html',
                          category_name=category_name,
                          cumulative_freq=[],
                          articles=[],
                          error_message=f"Error analyzing category: {str(e)}")


def get_category_articles(category_name):
    """Get all articles in a Wikipedia category"""
    url = "https://en.wikipedia.org/w/api.php"
    
    # Format category name
    if not category_name.startswith("Category:"):
        category_name = f"Category:{category_name}"
    
    articles = []
    cmcontinue = None
    
    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category_name,
            "cmlimit": 500,  # Max allowed by API
            "cmtype": "page",  # Only get articles, not subcategories
            "format": "json"
        }
        
        if cmcontinue:
            params["cmcontinue"] = cmcontinue
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if 'query' in data and 'categorymembers' in data['query']:
            for member in data['query']['categorymembers']:
                articles.append(member['title'])
        
        if 'continue' in data and 'cmcontinue' in data['continue']:
            cmcontinue = data['continue']['cmcontinue']
        else:
            break
    
    return articles


def analyze_wikipedia_article(title):
    # Format the title for the URL
    formatted_title = title.replace(' ', '_')
    url = f"https://en.wikipedia.org/wiki/{formatted_title}"

    # Get the article content
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(
            f"Failed to retrieve article. Status code: {response.status_code}")

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
    words = text.split()
    word_count = len(words)
    sentence_count = len(re.split(r'[.!?]+', text))
    avg_word_length = sum(len(word) for word in words) / word_count if word_count > 0 else 0

    # Find most common words (excluding common stop words)
    stop_words = {'the', 'a', 'an', 'and', 'in', 'to', 'of', 'for', 'on', 'with',
                  'as', 'by', 'at', 'from', 'was', 'were', 'is', 'are', 'it', 's', 'or',
                  'that', 'this', 'be', 'not', 'which', 'have', 'has', 'had', 'can',
                  'will', 'would', 'should', 'could', 'their', 'they', 'them', 'these',
                  'those', 'its', 'it\'s', 'there', 'than', 'then', 'when', 'where',
                  'who', 'whom', 'whose', 'what', 'why', 'how', 'all', 'any', 'both',
                  'each', 'few', 'more', 'most', 'some', 'such', 'no', 'nor', 'too',
                  'very', 'one', 'every', 'least', 'less', 'many', 'now', 'ever', 'also'}
    
    words = [word.lower() for word in re.findall(r'\b\w+\b', text)
             if word.lower() not in stop_words and len(word) > 1]
    
    # Get word frequencies
    word_freq = Counter(words)
    common_words = word_freq.most_common(10)
    
    # Calculate cumulative frequency
    total_words = len(words)
    cumulative_freq = []
    running_sum = 0
    
    for word, count in sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:50]:
        freq = count / total_words
        running_sum += freq
        cumulative_freq.append({
            'word': word,
            'count': count,
            'frequency': freq,
            'cumulative_frequency': running_sum
        })

    return {
        'title': title,
        'url': url,
        'word_count': word_count,
        'sentence_count': sentence_count,
        'avg_word_length': round(avg_word_length, 2),
        'common_words': common_words,
        'word_freq': dict(word_freq),
        'cumulative_freq': cumulative_freq,
        'excerpt': text[:500] + '...' if len(text) > 500 else text
    }


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
