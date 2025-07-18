#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EC商品ページ自動作成システム - Flask版
ASINからAmazon商品情報を取得し、楽天用商品ページを自動生成

必要なライブラリ:
pip install flask requests beautifulsoup4 python-dotenv
"""

from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import re
import os
from datetime import datetime
from dotenv import load_dotenv
import logging

# 環境変数を読み込み（.envファイルからAPIキーなどを取得）
load_dotenv()

# Flaskアプリケーションを初期化
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# ログ設定（エラーや処理状況を記録）
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AmazonProductScraper:
    """Amazon商品情報を取得するクラス"""
    
    def __init__(self):
        # ユーザーエージェント（ブラウザを偽装してアクセス）
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'ja-JP,ja;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    def get_product_info(self, asin):
        """
        ASINからAmazon商品情報を取得
        
        Args:
            asin (str): Amazon商品のASIN（10桁の英数字）
            
        Returns:
            dict: 商品情報辞書
        """
        try:
            # AmazonのURL作成
            url = f"https://www.amazon.co.jp/dp/{asin}"
            logger.info(f"Amazon商品情報取得開始: {url}")
            
            # Amazonページにアクセス
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()  # HTTPエラーをチェック
            
            # HTMLを解析
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 商品情報を抽出
            product_data = self._extract_product_data(soup, asin)
            
            logger.info(f"商品情報取得完了: {product_data['title'][:50]}...")
            return product_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Amazon接続エラー: {str(e)}")
            raise Exception(f"Amazon接続エラー: {str(e)}")
        except Exception as e:
            logger.error(f"商品情報取得エラー: {str(e)}")
            raise Exception(f"商品情報取得エラー: {str(e)}")
    
    def _extract_product_data(self, soup, asin):
        """
        BeautifulSoupオブジェクトから商品データを抽出
        
        Args:
            soup: BeautifulSoupオブジェクト
            asin: 商品ASIN
            
        Returns:
            dict: 抽出した商品情報
        """
        product_data = {
            'asin': asin,
            'title': '',
            'price': '',
            'description': '',
            'images': [],
            'features': [],
            'brand': '',
            'category': ''
        }
        
        # 商品名を取得（複数のセレクタを試す）
        title_selectors = [
            '#productTitle',
            '.product-title',
            'h1.a-size-large'
        ]
        
        for selector in title_selectors:
            title_element = soup.select_one(selector)
            if title_element:
                product_data['title'] = title_element.get_text().strip()
                break
        
        # 価格を取得（複数のパターンを試す）
        price_selectors = [
            '.a-price-whole',
            '.a-price.a-text-price.a-size-medium.apexPriceToPay .a-offscreen',
            '.a-price-range .a-price .a-offscreen',
            '#price_inside_buybox'
        ]
        
        for selector in price_selectors:
            price_element = soup.select_one(selector)
            if price_element:
                price_text = price_element.get_text().strip()
                # 数字のみを抽出
                price_numbers = re.findall(r'[\d,]+', price_text)
                if price_numbers:
                    product_data['price'] = f"¥{price_numbers[0]}"
                break
        
        # 商品説明を取得
        description_selectors = [
            '#feature-bullets ul',
            '#productDescription p',
            '.a-unordered-list.a-vertical.a-spacing-mini'
        ]
        
        description_parts = []
        for selector in description_selectors:
            elements = soup.select(f'{selector} li')
            for element in elements:
                text = element.get_text().strip()
                if text and len(text) > 10:  # 短すぎるテキストは除外
                    description_parts.append(text)
        
        product_data['description'] = '\n'.join(description_parts[:5])  # 最大5個まで
        
        # 商品画像を取得
        image_selectors = [
            '#landingImage',
            '.a-dynamic-image',
            '#imgTagWrapperId img'
        ]
        
        for selector in image_selectors:
            img_elements = soup.select(selector)
            for img in img_elements:
                src = img.get('src') or img.get('data-src')
                if src and 'amazon' in src:
                    product_data['images'].append(src)
                if len(product_data['images']) >= 5:  # 最大5枚まで
                    break
            if product_data['images']:
                break
        
        # ブランド名を取得
        brand_selectors = [
            '#bylineInfo',
            '.a-row .a-size-small.a-color-secondary',
            '#brand'
        ]
        
        for selector in brand_selectors:
            brand_element = soup.select_one(selector)
            if brand_element:
                brand_text = brand_element.get_text().strip()
                if 'ブランド' in brand_text or 'Brand' in brand_text:
                    product_data['brand'] = brand_text.replace('ブランド:', '').replace('Brand:', '').strip()
                break
        
        return product_data

class RakutenProductGenerator:
    """楽天用商品ページ生成クラス"""
    
    def __init__(self):
        self.profit_margin = 1.15  # 利益率15%を設定
    
    def generate_rakuten_product(self, amazon_data):
        """
        Amazon商品データから楽天用商品データを生成
        
        Args:
            amazon_data (dict): Amazon商品データ
            
        Returns:
            dict: 楽天用商品データ
        """
        logger.info(f"楽天商品データ生成開始: {amazon_data['title'][:50]}...")
        
        # 楽天用商品データを作成
        rakuten_data = {
            'item_name': self._optimize_title(amazon_data['title']),
            'item_price': self._calculate_price(amazon_data['price']),
            'item_description': self._generate_description(amazon_data),
            'catch_copy': self._generate_catch_copy(amazon_data),
            'item_url': self._generate_item_url(amazon_data['title']),
            'images': amazon_data['images'],
            'category_id': self._suggest_category(amazon_data),
            'keywords': self._generate_keywords(amazon_data),
            'original_asin': amazon_data['asin']
        }
        
        logger.info("楽天商品データ生成完了")
        return rakuten_data
    
    def _optimize_title(self, title):
        """楽天用にタイトルを最適化"""
        # 楽天の文字数制限（128文字）に合わせて調整
        if len(title) > 120:
            title = title[:120] + "..."
        
        # 楽天でよく使われるキーワードを追加
        keywords_to_add = ['送料無料', '即納', '高品質']
        
        for keyword in keywords_to_add:
            if keyword not in title and len(title) + len(keyword) + 3 <= 128:
                title = f"{title} 【{keyword}】"
                break
        
        return title
    
    def _calculate_price(self, amazon_price):
        """利益を考慮した楽天価格を計算"""
        try:
            price_str = re.sub(r'[¥,]', '', amazon_price)
            amazon_price_int = int(price_str)
            rakuten_price = int(amazon_price_int * self.profit_margin)
            
            if rakuten_price < 1000:
                rakuten_price = ((rakuten_price + 49) // 50) * 50
            else:
                rakuten_price = ((rakuten_price + 99) // 100) * 100
            
            return rakuten_price
        except (ValueError, TypeError):
            logger.warning(f"価格解析エラー: {amazon_price}")
            return 0
    
    def _generate_description(self, amazon_data):
        """楽天用商品説明を生成"""
        description_parts = []
        description_parts.append("■商品の特徴")
        description_parts.append(amazon_data['description'])
        
        if amazon_data['brand']:
            description_parts.append(f"\n■ブランド\n{amazon_data['brand']}")
        
        description_parts.append("\n■配送・サービス")
        description_parts.append("・全国送料無料でお届け")
        description_parts.append("・迅速発送を心がけております")
        
        return '\n'.join(description_parts)
    
    def _generate_catch_copy(self, amazon_data):
        """楽天用キャッチコピーを生成"""
        if amazon_data['brand']:
            return f"{amazon_data['brand']}の人気商品！送料無料でお届け"
        return "人気商品！送料無料でお届け"
    
    def _generate_item_url(self, title):
        """楽天用商品URLを生成"""
        url_safe = re.sub(r'[^a-zA-Z0-9]', '', title.lower())
        if len(url_safe) > 50:
            url_safe = url_safe[:50]
        timestamp = datetime.now().strftime("%Y%m%d")
        return f"{url_safe}_{timestamp}"
    
    def _suggest_category(self, amazon_data):
        """楽天カテゴリを提案"""
        category_keywords = {
            '100804': ['健康', 'サプリ'],
            '100026': ['電子', 'PC'],
            '100227': ['キッチン', '家電'],
            '100938': ['美容', 'コスメ'],
            '101070': ['ファッション', '服']
        }
        
        title_lower = amazon_data['title'].lower()
        for category_id, keywords in category_keywords.items():
            for keyword in keywords:
                if keyword in title_lower:
                    return category_id
        return '100000'
    
    def _generate_keywords(self, amazon_data):
        """楽天用検索キーワードを生成"""
        keywords = []
        title_words = amazon_data['title'].split()
        for word in title_words[:5]:
            clean_word = re.sub(r'[^\w]', '', word)
            if len(clean_word) > 1:
                keywords.append(clean_word)
        
        if amazon_data['brand']:
            keywords.append(amazon_data['brand'])
        
        keywords.extend(['送料無料', '高品質', '人気'])
        unique_keywords = list(dict.fromkeys(keywords))[:10]
        return ','.join(unique_keywords)

# Flaskルート定義
@app.route('/')
def index():
    """メインページ"""
    return render_template('index.html')

@app.route('/api/generate', methods=['POST'])
def generate_product_page():
    """ASIN入力から商品ページ生成APIエンドポイント"""
    try:
        data = request.get_json()
        asin = data.get('asin', '').strip()
        
        if not asin or len(asin) != 10:
            return jsonify({'error': 'ASINを正しく入力してください'}), 400
        
        scraper = AmazonProductScraper()
        amazon_data = scraper.get_product_info(asin)
        
        generator = RakutenProductGenerator()
        rakuten_data = generator.generate_rakuten_product(amazon_data)
        
        result = {
            'success': True,
            'amazon_data': amazon_data,
            'rakuten_data': rakuten_data,
            'generated_at': datetime.now().isoformat()
        }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"商品ページ生成エラー: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/preview/<asin>')
def preview_product(asin):
    """生成した商品ページのプレビュー"""
    try:
        scraper = AmazonProductScraper()
        amazon_data = scraper.get_product_info(asin)
        
        generator = RakutenProductGenerator()
        rakuten_data = generator.generate_rakuten_product(amazon_data)
        
        return render_template('preview.html', 
                             amazon_data=amazon_data, 
                             rakuten_data=rakuten_data)
        
    except Exception as e:
        logger.error(f"プレビューエラー: {str(e)}")
        return render_template('error.html', error=str(e))

if __name__ == '__main__':
    # 開発用サーバーを起動
    app.run(debug=True, host='0.0.0.0', port=5000)
