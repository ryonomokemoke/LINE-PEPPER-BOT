from typing import Any
import dotenv
import os

from flask import Flask, request, abort ,jsonify
from flask_cors import CORS
import json

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage, CarouselTemplate, CarouselColumn, FollowEvent,
    JoinEvent
)

import re # 文字列
import datetime # 登録日など日付

### Hotpepperでのウェブスクレイピング用
import requests
from bs4 import BeautifulSoup

### UserTutorialのimport
from UserTutorial import TutorialMessages
### SearchQueryのimport
from SearchQuery import SearchQuery

# カルーセルURIでのエスケープ用
import urllib.parse

# sqlite3(RDBMS)
import sqlite3
from Database import sqlite as db

dotenv.load_dotenv(verbose=True)
line_bot_api = LineBotApi(os.environ["LINE_BOT_CHANNEL_ACCESS_TOKEN"])
handler = WebhookHandler(os.environ["LINE_BOT_CHANNEL_SECRET"])
SEARCH_FORM_LIFF = os.environ['SEARCH_FORM_LIFF']
SHARE_LIFF_BASE_URI = os.environ["SHARE_LIFF_BASE_URI"]
HOTPEPPRE_API_KEY = os.environ["HOTPEPPRE_API_KEY"]


app = Flask(__name__)
CORS(app)

@app.route("/callback", methods=['POST'])
def callback():
    '''
    Lineサーバーの要求に対してngrokサーバーが返答する。
    この結果をラインサーバが受け取って、通信できているか見る。
    '''
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

@app.route('/user_query', methods = ['GET'])
def user_query():
    """ユーザーの検索条件を返すエンドポイント

    Returns:
        json : json型で、{date: , place: , budget:, freeword:}を返す。
    """
    # クエリパラメータからuser_idを取得
    user_id = request.args.get('user_id')
    # user_queriesを取得
    user_queries = db.get_user_queries(DATABASE_PATH, user_id)[1:5]

    print(user_queries)
    user_queries_json = jsonify(user_queries)
    response = json.dumps(user_queries, ensure_ascii=False)
    # 取得したデータをJSON形式で返す
    return response


@app.route('/shop_info', methods = ['GET'])
def fetch_shop_info():
    """店舗情報をを返すエンドポイント

    Returns:
        json : json型で、{}を返す。
    """
    # クエリパラメータからuser_idを取得
    shop_id = request.args.get('shop_id')
    # shop_recordを取得
    shop_record = db.fetch_shop_record(DATABASE_PATH, shop_id) # jumpppp
    # fetchした店舗情報をjson形式にする
    response = shop_record.to_json()
    print("respons: " + response)
    # レスポンスとしてJSON形式で返す
    return response


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    '''
    メッセージに反応する。実質main関数
    '''
    # ユーザーidを取得
    user_id = get_user_id_from_event(event)

    # 受け取ったtextを標準化。(英数字の半角統一など)
    standardized_message = SearchQuery.standardize_message(event.message.text)
    print(f'std_msg:{standardized_message}')

    # 次の5件を表示する場合
    if standardized_message == "次の5件":
        if not db.has_search_record(DATABASE_PATH, user_id):
            # 店舗検索がヒットしなかった際のフィードバックメッセージ作成
            cannot_introduce_message = create_has_no_more_shop_message(db.get_query_record(DATABASE_PATH, user_id))
            # ユーザーにメッセージ送信
            line_bot_api.reply_message(event.reply_token, cannot_introduce_message)
            return
        
        # ユーザーに店舗を紹介（DBより店舗選出、店舗情報upsert、カルーセルメッセージ作成&送信）
        introduce_shops_by_user_id(event, DATABASE_PATH, user_id)
        return
    
    # お気に入り店舗を表示する場合
    if standardized_message == "お気に入り店舗一覧":
        return


    # 検索条件記号がない場合はtextを無視する。
    if not SearchQuery.has_query_marks(standardized_message, query_marks):
        return

    # 新規ユーザーの場合、初期Queryレコードを設定
    if db.is_new_user(DATABASE_PATH, user_id):
        db.add_user_record(DATABASE_PATH, user_id) # ユーザーUserテーブルに登録
        db.add_empty_query_record(DATABASE_PATH, user_id) # 条件NULLのみのQueryレコードを作成。

    # 検索条件の更新
    input_queries = SearchQuery.split_to_each_query_texts(standardized_message, query_marks) # 検索条件をリストで作成　修正　SearchQueryクラスのメソッドにしたい。
    input_queries[0] = input_queries[0].replace("-","") # yyyy-mm-dd を yyyymmdd に変更
    print(f'input_queries:{input_queries}')
    db.update_query(DATABASE_PATH, user_id, input_queries) # Queryレコードを更新

    # 検索条件からホットペッパー検索URLを生成
    queries = db.get_user_queries(DATABASE_PATH, user_id) # ユーザーの検索条件を取得
    user_query = SearchQuery.UserQuery(queries) # 検索条件情報を持つインスタンスを作成
    original_search_url = user_query.hotpepper_search_url() # 検索URLを生成

    # 検索URLをもとに、複数のヒット店舗一覧ページURLのリストを取得
    original_search_url_response = requests.get(original_search_url)
    original_search_url_soup = BeautifulSoup(original_search_url_response.text, 'html.parser')
    search_result_urls = get_search_result_urls(original_search_url, original_search_url_soup, MAX_HIT_PAGE_STOCK_QUANTITY)

    ## 一件も店がヒットしなかった時 # 「店舗としてはヒットするが、情報が入っていない」店が除去できていない(要修正)
    if search_result_urls == None:
        # 店舗検索がヒットしなかった際のフィードバックメッセージ作成s
        cannot_introduce_message = create_shop_not_hit_carousel_column(db.get_query_record(DATABASE_PATH, user_id))
        # ユーザーにメッセージ送信
        line_bot_api.reply_message(event.reply_token, cannot_introduce_message)
        return
        
    ## 1店舗以上ヒットした時 
    # 紹介候補となる shop_ids をurlから取得　（修正）それをSearchレコードとして追加。
    search_hit_shop_ids = get_shop_ids_by_search_urls(search_result_urls)
    # Searchレコードの更新
    db.delete_all_search_records(DATABASE_PATH, user_id) # 以前のSearchレコードを全削除。
    db.add_search_records(DATABASE_PATH, user_id, search_hit_shop_ids)

    # ユーザーに店舗を紹介（DBより店舗選出、店舗情報upsert、カルーセルメッセージ作成&送信、送信済みDB更新）
    introduce_shops_by_user_id(event, DATABASE_PATH, user_id)

    return

@handler.add(FollowEvent)
def handle_follow(event):
    '''
    Botフォロー時のメッセージ
    '''
    # 友達追加時にフレックスメッセージを送信
    line_bot_api.reply_message(
        event.reply_token,
        join_message
    )


@handler.add(JoinEvent)
def handle_join(event):
    '''
    Botをグループに参加させた時のメッセージ
    '''
    # グループ追加時にフレックスメッセージを送信
    line_bot_api.reply_message(
        event.reply_token,
        join_message
    )


class QueryMarks:
    def __init__(self):
        self._date = DateMark()
        self._price = PriceMark()
        self._place = PlaceMark()
        self._freeword = FreewordMark()

    @property
    def date(self):
        return self._date
    @property
    def price(self):
        return self._price
    @property
    def place(self):
        return self._place
    @property
    def place(self):
        return self._freeword

class DateMark:
    def __init__(self):
        self.mark = "/"
        self.handling = False # スペースを含めない。マークからスペースや改行までの間の文字列を取得。
class PriceMark:
    def __init__(self):
        self.mark = "¥"
        self.handling = False # スペースを含めない。マークからスペースや改行までの間の文字列を取得。
class PlaceMark:
    def __init__(self):
        self.mark = "+"
        self.handling = False # スペースを含めない。マークからスペースや改行までの間の文字列を取得。
class FreewordMark:
    def __init__(self):
        self.mark = "="
        self.handling = True # スペースを含める。マークから改行までの間の文字列を取得。


class ShopCarusel:

    def __init__(self, shop_record):
        
        # 店舗説明分の作成
        shop_discription = create_shop_discription_for_carousel(shop_record)

        # CarouselColumnの仕様: title<=40文字, text<=60文字　に合わせる
        trimed_shop_name = trim_text(shop_record.name, max_length=40)
        trimed_shop_discription = trim_text(shop_discription, max_length=60)

        self.carousel_column = CarouselColumn(
            thumbnail_image_url = shop_record.img_url,
            title = trimed_shop_name,
            text = trimed_shop_discription, 
            actions=[
                {
                    "type": "uri",
                    "label": "詳しくみる",
                    "uri": shop_record.affiliate_url # 店舗アフィリンク
                },
                {
                    "type": "uri",
                    "label": "共有する",
                    "uri": SHARE_LIFF_BASE_URI + "?shop_id=" + shop_record.shop_id
                }
            ]
        )


class ShopRecord: # jumpppp
    """shop_carousel作成に必要十分な情報を取得するクラス。
    情報元はShopDetail(retrieve)もしくはDB(fetch)。
    """
    def __init__(self):
        self.id = None
        self.shop_id = None
        self.name = None
        self.img_url = None
        self.access = None
        self.affiliate_url = None
        self.review_score = None
        self.review_quantity = None
    
    def to_json(self):
        """json形式にして全プロパティを返す

        Returns:
            json: 全プロパティ
        """
        return json.dumps(self.__dict__, ensure_ascii=False)

    def retrieve_propaties_from_shop_detail(self, shop_detail):
        """ ShopDetailインスタンスから、Shopレコード情報を取得。
        "retrieve" :もう既に存在する情報を取得する

        Args:
            shop_detail (ShopDetail): shop_carousel作成に十分な情報を持つインスタンス
        """
        self.shop_id = shop_detail.shop_id
        self.name = shop_detail.name
        self.img_url = shop_detail.img_url
        self.access = shop_detail.access
        self.affiliate_url = shop_detail.affiliate_url
        self.review_score = shop_detail.review_score
        self.review_quantity = shop_detail.review_quantity


class ShopDetail:
    """shop_carousel作成に十分な情報をHotpepperAPIとスクレイピングで取得
    """

    def __init__(self, shop_id):
        self.shop_id = shop_id
        self.set_shop_record_info_by_hotpepper_api()


    def set_shop_record_info_by_hotpepper_api(self):        
        '''
        DBに登録する情報を設定する。（shop_idのみインスタンス時に設定済み。）
        '''
        # ショップの全情報をプロパティに格納(HotpepperAPIによる)
        self.set_shop_detail_by_hotpepper_api() 
        
        # カルーセルに必要な情報や更新日時などをプロパティに設定
        self.name = trim_text(self.shop_detail['name'])
        self.img_url = self.shop_detail['photo']['pc']['l']
        self.access = self.shop_detail['mobile_access']
        self.affiliate_url = get_affiliate_url(self.shop_id)
        self.review_score, _, self.review_quantity = get_shop_review(self.shop_id) # レビューのみAPIで取れないのでスクレイピング
        
        self.update_date = datetime.datetime.now(datetime.timezone.utc) # 現在を更新日時に設定（一応タイムゾーンあり）


    def set_shop_detail_by_hotpepper_api(self):
        '''
        ショップの全情報をプロパティに格納(HotpepperAPIによる)
        '''
        # APIを使うための初期設定。
        HOTPEPPER_API_BASE_URL = 'http://webservice.recruit.co.jp/hotpepper/gourmet/v1/'

        # 検索内容の定義。
        params = {
            'key': HOTPEPPRE_API_KEY,
            'id': self.shop_id,
            'format': 'json',
            'count': 1
        }
        # 店舗情報取得(公式テンプレ)
        response = requests.get(HOTPEPPER_API_BASE_URL, params)
        datum = response.json()
        # J000132150のように、なぜか取れない奴がいる。 {'results': {'api_version': '1.30', 'results_available': 0, 'results_returned': '0', 'results_start': 0, 'shop': []}}
        
        self.shop_detail = datum['results']['shop'][0]


class QueryRecord:

    def __init__(self):
        self.date = None
        self.place = None
        self.price = None
        self.freeword = None

    def text_for_carousel(self):
        
        self.date_disp = str(self.date) if self.date else ""
        self.place_disp = str(self.place) if self.place else ""
        self.price_disp = str(self.price) if self.price else ""
        self.freeword_disp = str(self.freeword) if self.freeword else ""

        display_text_for_carousel = "/" + self.date_disp + "\n" \
                                    "+" + self.place_disp + "\n" \
                                    "¥" + self.price_disp + "\n" \
                                    "=" + self.freeword_disp

        return display_text_for_carousel


def introduce_shops_by_user_id(event, DATABASE_PATH: str, user_id: str):
    """ ユーザーに店舗を紹介（DBより店舗選出、店舗情報upsert、カルーセルメッセージ作成&送信、送信済みDB更新）


    Args:
        event (Any): ラインボットのメッセージイベント
        DATABASE_PATH (str): DBのファイルパス
        user_id (str): user_id
    """

    # Searchレコードと対応するshop_idの選出
    selected_search_record_ids, selected_shop_ids = db.select_shop(DATABASE_PATH, user_id, MAX_DISPLAY_SHOP_QUANTITY)

    # 検索条件の取得
    query_record = db.get_query_record(DATABASE_PATH, user_id) 

    # 紹介するShopRecordリストの取得
    shop_records = create_shop_records(DATABASE_PATH, selected_shop_ids)

    # 店舗紹介カルーセルメッセージ作成
    carousel_messages = create_carousel_messages(shop_records, query_record)

    # ユーザーにメッセージ送信
    line_bot_api.reply_message(event.reply_token, carousel_messages)

    # 提案済みのSearchレコードを削除
    db.delete_select_search_record(DATABASE_PATH, selected_search_record_ids) # Searchレコードの削除　(確認 複数人の並列処理でsearch_record_idがずれることがあるか？ 


def create_carousel_messages(shop_records: list, query_record) -> TemplateSendMessage:
    """指定店舗idを紹介する、ユーザーに送信するカルーセルメッセージを作成

    Args:
        DATABASE_PATH (str): _description_
        shop_records (list): Shopレコードのリスト

    Returns:
        TemplateSendMessage: 店舗紹介カルーセルメッセージ(必須カルーセルつき)
    """

    # カルーセルメッセージの作成
    carousel_columns = create_shop_carousel_columns(shop_records)
    carousel_columns.append(get_neccessory_carousel_column(query_record)) # 必須カルーセル（オプションカルーセル）追加

    # 送信用のカルーセル方式のメッセージを作成
    carousel_messages = TemplateSendMessage(
        alt_text='飲食店一覧',
        template=CarouselTemplate(carousel_columns)
    )

    return carousel_messages


def create_shop_records(DATABASE_PATH: str, shop_ids: list) -> list:
    """店舗idリストからShopRecordリストを取得

    Args:
        DATABASE_PATH (str): DBのファイルパス
        shop_ids (list): shop_idリスト

    Returns:
        list[ShopRecord]: ShopRecordリスト
    """
    # shop_idsを Shopテーブルにある/ない で分ける 
    registered_shop_ids = db.extract_registered_shop_ids(DATABASE_PATH, shop_ids) # DBに登録済みのshop_idリスト 修正:更新が古いものはnew扱いしたいかも
    new_shop_ids = list_subtract(shop_ids, registered_shop_ids) # DBに未登録のshop_idリスト

    # Shopテーブルにある/ない のそれぞれで Shopレコードリストを作成
    registered_shop_record_list = create_registered_shop_records(DATABASE_PATH, registered_shop_ids)
    new_shop_record_list = create_new_shop_records(DATABASE_PATH, new_shop_ids) # DBへの登録も行う

    return registered_shop_record_list + new_shop_record_list # 要素を足し合わせたリスト



def create_registered_shop_records(DATABASE_PATH: str, registered_shop_ids: list) -> list:
    """DBに登録のある店舗idリストについて、DBからShopRecordリストを取得

    Args:
        DATABASE_PATH (str): DBのファイルパス
        new_shop_ids (list): DBに登録のないshop_idリスト

    Returns:
        list[ShopRecord]: ShopRecordリスト
    """
    # ShopCarousel作成用のShopRecordリスト
    shop_records = []

    # DBに登録済みの店舗のShopRecordリストを取得
    if registered_shop_ids:
        for shop_id in registered_shop_ids:
            # DBからShopRecordインスタンスを作成
            shop_record = db.fetch_shop_record(DATABASE_PATH, shop_id)
            # ShopRecordリストに追加
            shop_records.append(shop_record)
            # インスタンスの解放
            del shop_record

    return shop_records


def create_new_shop_records(DATABASE_PATH: str, new_shop_ids: list) -> list:
    """DBに登録のない店舗idリストについて、apiとスクレイピングでShopRecordリストを取得
    新規店舗なため、得た情報のDB登録も行う。

    Args:
        DATABASE_PATH (str): DBのファイルパス
        new_shop_ids (list): DBに登録のないshop_idリスト

    Returns:
        list[ShopRecord]: ShopRecordリスト
    """
    shop_records = []

    # 新規店舗があれば、情報を取得してDBに登録
    if new_shop_ids:
        for shop_id in new_shop_ids:
            print(shop_id)
            # 店舗レコード登録に必要な情報を設定
            shop_detail = ShopDetail(shop_id) # apiとスクレイピングでカルーセル作成に十分な情報を取得
            shop_record = ShopRecord() # ShopRecordをプロパティNoneでインスタンス化
            shop_record.retrieve_propaties_from_shop_detail(shop_detail)
            # 店舗レコードをDBに登録
            db.add_shop_record(DATABASE_PATH, shop_record)
            # ShopRecordリストに追加
            shop_records.append(shop_record)

        # インスタンスへの参照を削除
        del shop_detail
        del shop_record

    return shop_records


def create_shop_carousel_columns(shop_records: list) -> list:
    """店舗レコードリストから生成した店舗CarouselColumnのリスト
    これをもとにカルーセルメッセージを生成。

    Args:
        shop_records (list[ShopRecord]): Shopテーブルから取得できる各店舗情報のリスト

    Returns:
        list[CarouselCoulumn]: カルーセルメッセージを生成するのに必要な店舗CarouselColumnインスタンスのリスト。
    """
    carousel_columns = [] # return

    # 各店舗に対してカルーセルメッセージを作成。
    for shop_record in shop_records:

        # ShopRecordインスタンスからShopCarouselインスタンス作成
        shop_carousel = ShopCarusel(shop_record)
        # carousel_columnをappend
        carousel_columns.append(shop_carousel.carousel_column) #jump

    return carousel_columns


def create_shop_discription_for_carousel(shop_record: ShopRecord) -> str:
    """店舗カルーセルの詳細文面の作成。 現在はアクセスと評価が入れてる。

    Args:
        shop_record (ShopRecord): ShopRecordインスタンス

    Returns:
        str: 店舗カルーセルの詳細文面
    """
        
    # レビューのある店舗の場合
    if shop_record.review_score:
        discription_text = shop_record.access + "\n" \
                + f"{shop_record.review_score:.1f}" + " " + db.shop_reputation(shop_record.review_score) + "\n" \
                + str(shop_record.review_quantity) + "件のレビューの総評"
    # レビューのない店舗の場合
    else:
        discription_text = shop_record.access

    return discription_text


def extract_number_from_string(s: str) -> int:
    """文字列から数字の部分をint型で返す。("12件の~" → 12、"212件の~" → 212)

    Args:
        s (str): _description_

    Returns:
        int: 文字列の初めに連続する数字。ただし数字から始まらないとNone
    """
    numbers = re.findall(r'\d+', s)  # 文字列から数字の部分を抽出
    if numbers:
        return int(numbers[0])  # 抽出された数字のリストから最初の要素をint型に変換して返す
    else:
        return None  # 数字が見つからない場合はNoneを返す（またはエラー処理など）
    

def get_shop_review(shop_id: str) -> Any:
    """shop_idから評価を取得。評価がない場合はNoneを返す。

    Args:
        shop_id (str): shop_id。

    Returns:
        float: review_score : 1.0~5.0 のホットペッパーの評価値
        str: reputation : VeryGoodとか。 (修正) そもそも入らなそうだけど、正規化してDB読み込みにしたほうがスッキリ？
        int: review_quantity : レビュー総数
    """
  
    #店舗URL
    shop_url = "https://www.hotpepper.jp/str" + shop_id + "/"
    
    # HTTP GETリクエストを送信してHTMLを取得
    response = requests.get(shop_url)
    html = response.text
    
    # BeautifulSoupを使用してHTMLを解析
    soup = BeautifulSoup(html, 'html.parser')
    
    # ratingScoreを含む要素 ratingWrap を検索して取得
    rating_wrap_element = soup.find('div', class_='ratingWrap')

    # ratingWrap を取得できなかった場合 None でreturn
    if not rating_wrap_element:
        return None, None, None
    
    # --- 以下、ratingWrap を取得できた場合 ----
    # レビュー情報を取得。
    review_score: float = float(rating_wrap_element.find('span', class_='ratingScoreValue').text) # 3.6
    reputation: str = rating_wrap_element.find('span', class_='ratingScoreText').text # "Very Good"
    review_quantity_str: str = rating_wrap_element.find('span', class_='ratingReivew').text # '241件のレビューの総評'
    review_quantity = extract_number_from_string(review_quantity_str) # 241
    
    return review_score, reputation, review_quantity


def sort_shop_ids_by_rated(stock_shop_ids: list) -> list:
    """ 店舗リストを レビューあり→レビューなしの順にソートする。

    Args:
        stock_shop_ids (list[str]): ホットペッパー検索で取得した店舗idリスト。

    Returns:
        list[str]: レビューあり → レビューなし の順に並べ直した店舗idリスト。
    """
    # レビューありの shop_id のみ抽出
    rated_shop_ids = get_rated_shop_ids(stock_shop_ids)

    # レビューなし店舗リスト。（stock_shop_ids から rated_shop_ids の要素を取り除いたリスト）
    not_rated_shop_ids = [x for x in stock_shop_ids if x not in rated_shop_ids]

    # レビューあり店舗id → レビューなし店舗id となるようソート
    sorted_shop_ids = rated_shop_ids + not_rated_shop_ids

    return sorted_shop_ids


def extract_introduce_shop_ids(stock_shop_ids: list) -> list:
    """実際に紹介するshop_idsを選択して返す。

    Args:
        stock_shop_ids (list[str]): ホットペッパーの検索結果urlから取得したshop_idリスト。

    Returns:
        list[str]: 実際に紹介するshop_ids 
    """

    # 店舗リストを レビューあり→レビューなしの順にソートする。
    sorted_shop_ids = sort_shop_ids_by_rated(stock_shop_ids)

    # 表示可能な最大店舗数を取得
    display_shop_quantity = min(len(stock_shop_ids), MAX_DISPLAY_SHOP_QUANTITY)

    return sorted_shop_ids[:display_shop_quantity] # 表示可能な最大数のレビューなし店舗リスト


def get_rated_shop_ids(shop_ids: list) -> list:
    """shop_ids のうち、レビューのある shop_id のみをappendして返す。

    Args:
        shop_ids (list): _description_

    Returns:
        list: _description_
    """
    '''
    
    '''

    has_rate_shop_ids = []

    for current_shop_id in shop_ids:
        # shop_id からレビューを取得
        shop_rate = get_shop_review(current_shop_id)
        # レビューがあればappend
        if shop_rate:
            has_rate_shop_ids.append(current_shop_id)
        
        # 最終的なカルーセル表示数に到達したら抜き出しを終了
        if len(has_rate_shop_ids) >= MAX_DISPLAY_SHOP_QUANTITY:
            break

    return has_rate_shop_ids


def create_shop_not_hit_carousel_column(query_record) -> TemplateSendMessage:
    '''
    検索がヒットしなかったことを伝えるメッセージを返す。
    現在の検索条件もユーザーにフィードバックする。
    '''

    shop_not_hit_carousel_column = CarouselColumn(
        thumbnail_image_url="https://document.intra-mart.jp/library/rpa/public/im_rpa_usage_guide/_images/winactor_tutorial_5_4_1.png",
        title="こちらの条件ではお店がヒットしませんでした。",
        text= query_record.text_for_carousel(),
        actions=[
            {
                "type": "uri",
                "label": "検索条件を変更する",
                "uri": SEARCH_FORM_LIFF # フォームLIFF
            },
            {
                "type": "message",
                "label": "お気に入り店舗一覧",
                "text": "お気に入り店舗一覧"
            }
        ]
    )

    # カルーセルテンプレートの作成
    shop_not_hit_carousel_column = TemplateSendMessage(
        alt_text = "no_more_shop_carousel_column",
        template = CarouselTemplate(columns=[shop_not_hit_carousel_column])
    )

    return shop_not_hit_carousel_column


def create_has_no_more_shop_message(query_record) -> TemplateSendMessage:
    '''
    検索がヒットしなかったことを伝えるメッセージを返す。
    現在の検索条件もユーザーにフィードバックする。
    '''

    shop_not_hit_carousel_column = CarouselColumn(
        thumbnail_image_url="https://document.intra-mart.jp/library/rpa/public/im_rpa_usage_guide/_images/winactor_tutorial_5_4_1.png",
        title="もうお店がありません。",
        text = "条件を変えて検索してみてください！\n" + query_marks.ext_for_carousel(),
        actions=[
            {
                "type": "uri",
                "label": "検索条件を変更する",
                "uri": "https://liff.line.me/2000472699-9WJ36mXE" # フォームLIFF
            },
            {
                "type": "message",
                "label": "お気に入り店舗一覧",
                "text": "お気に入り店舗一覧"
            }
        ]
    )

    # カルーセルテンプレートの作成
    no_more_shop_carousel_messages = TemplateSendMessage(
        alt_text = "no_more_shop_carousel_column",
        template = CarouselTemplate(columns=[shop_not_hit_carousel_column])
    )

    return no_more_shop_carousel_messages


def get_hit_shop_quantity(original_search_url_soup):
    '''
    url （例："https://www.hotpepper.jp/CSP/psh010/doBasic?FWT=餃子&SA=SA11&RDT=&SMK=&SLB=0&CBF=&CBT="）
    でヒットした店舗数を返す。
    
    入力は上記urlをもとに取得したsoup。
    '''
    hit_shop_quantity_html = original_search_url_soup.find('span', class_='fcLRed bold fs18 padLR3') # "<span class="fcLRed bold fs18 padLR3">6540</span>"
    hit_shop_quantity = int(hit_shop_quantity_html.text) # 6540
    
    return hit_shop_quantity


def get_search_result_urls(original_search_url: str, original_search_url_soup: BeautifulSoup, max_page_quantity: int) -> list:
    """ホットペッパー検索にヒットした複数ページ（上限あり）のurlリスト。

    Args:
        original_search_url (str): ユーザーのクエリを元に生成したホットペッパー検索url
        original_search_url_soup (BeautifulSoup): ホットペッパー検索結果の1ページ目のスクレイピングデータ。
        max_page_quantity (int): 取得する検索結果ページurlの最大数。
        
    Returns:
        list: 検索結果ページurlのリスト。最大max_page_quantity個。 1つもヒットしない場合はNoneを返す。
    """

    # 検索結果の総ページ数を取得
    hit_search_page_quantity = get_hit_search_page_quantity(original_search_url_soup)        

    # 該当店舗が１つもない場合、Noneを返す。
    if hit_search_page_quantity == None:
        print("original_search_url : " + original_search_url)
        print("None：該当店舗が見つかりませんでした。：get_search_result_urls")
        return None

    # 検索結果が1ページのみの時、ナンバリングurlではなくオリジナルurl（url１つ分）を返す。
    if hit_search_page_quantity == 1:
        return [original_search_url]

    # 検索結果が複数ページの場合、各ページを数字で表せる短縮ナンバリングURLに変換して扱う。
    # 短縮ナンバリングURLの共通部分を取得
    core_numbering_search_url = get_core_numbering_search_url(original_search_url_soup)
    # 短縮ナンバリングURLの配列作成
    search_result_urls = append_numbering_search_urls(core_numbering_search_url, hit_search_page_quantity, max_page_quantity)

    return search_result_urls


def append_numbering_search_urls(core_numbering_search_url, hit_search_page_quantity, max_search_page_quantity):
    '''
    core_numbering_search_url と hit_search_page_quantity から、
    最大 max_search_page_quantity 個のnubering_search_urlsを作成。
    '''
    numbering_search_urls = [] # return変数

    numbering_search_urls_quantity = min(hit_search_page_quantity, max_search_page_quantity)
    for current_page_index in range(numbering_search_urls_quantity):
        current_numbering_search_url = core_numbering_search_url + str(current_page_index + 1) + "/"
        numbering_search_urls.append(current_numbering_search_url)
    
    print(numbering_search_urls)
    return numbering_search_urls


def get_core_numbering_search_url(original_search_url_soup):
    '''
    該当店舗数が2ページ以上（=店舗数が23以上）の時のみ呼び出すこと。
    original_search_url_soupから、この検索条件のナンバリング短縮検索URLの共通部分を取得する。
    
    <ul class="pageLinkLinearBasic cf">
                            <li class="crt">
                                <span>1</span>
                            </li>
                            <li>
                                <a href="/SA11/fwt%E9%A4%83%E5%AD%90/bgn2/">
                            ...
    → "https://www.hotpepper.jp/SA11/fwt%E9%A4%83%E5%AD%90/bgn" を返す。
    '''

    second_page_li_index = 2 # lisのこの位置が2ページ目のURLを持ってる。
    hotpepper_url_domain = "https://www.hotpepper.jp" # hotpepperのドメイン部分

    # htmlのネストを掘っていく（修正）これだと該当店舗数が1ページの時で機能しない。もしくは複数ページの時と処理が変わる。
    ul = original_search_url_soup.find('ul', class_='pageLinkLinearBasic cf') # HTML全体からページ数クラスを抽出
    lis = ul.find_all('li')

    # ページ2 が入った li から、"/SA11/fwt%E9%A4%83%E5%AD%90/bgn" 部分を取得。
    number2_nubering_search_url = lis[second_page_li_index].find('a')['href']

    # "https://www.hotpepper.jp" + "/SA11/fwt%E9%A4%83%E5%AD%90/bgn"
    core_numbering_search_url = hotpepper_url_domain + number2_nubering_search_url[:len(number2_nubering_search_url)-2]

    return core_numbering_search_url


def get_hit_search_page_quantity(original_search_url_soup: BeautifulSoup) -> int:
    """ホットペッパー検索でヒットした全店舗がなすページ数

    Args:
        original_search_url_soup (BeautifulSoup): ホットペッパー検索結果の1ページ目のスクレイピングデータ。

    Returns:
        int: ホットペッパー検索でヒットした全店舗がなす総ページ数。 ヒット0件の時のみNoneを返す。
    """
    try:
        # 必ず表示される、ページ数が書かれたタグの内容(文字列)を取得　修正　findの結果がNoneのことがある
        page_quantity_sentence = original_search_url_soup.find('li', class_='lh27').text # "1/nnnページ"
    
    except AttributeError as e:
        # エラーが発生した場合の処理を記述します
        print(f"An error occurred: {e}")
        return None
    
    else:
        # ページ数部分のみを取得。（"1/nnnページ" → "nnn" → nnn）
        hit_search_page_quantity = int(page_quantity_sentence[len("1/") : len(page_quantity_sentence)-len("ページ")])
        return hit_search_page_quantity


def get_numbering_search_urls(original_search_url_soup): #リファクタリング
    '''
    検索条件URLでヒットしたshop_idを、MAX_DISPLAY_SHOP_QUANTITY個取得。(確認済み)
    '''

    # スクレイピングでヒットした店舗リストを取得(最大でmax_shop_quantity店舗。)
    html_search_page_quantity = original_search_url_soup.find_all('li', class_='crt')
    

    # 1店舗も検索がヒットしなかった場合、処理終了。
    if len(html_search_page_quantity) == 0:
        print("Error: could not find any shops")
        return None
    
    print(len(html_search_page_quantity))
    print(html_search_page_quantity)

    return True


def trim_text(text: str, max_length=40) -> str:
    """カルーセル店舗名41文字以上対策
    文字数がmax_length以上の場合、41文字以降を切り捨て、40文字目を"…"に変換する。

    Args:
        text (str): ホットペッパー上での店舗名
        max_length (int, optional): 文字列の最大数。 Defaults to 40.

    Returns:
        str: max_length以下に文字数をトリミングした文字列。
    """

    # 文字数が上限を超えない時、元の文字列をそのまま返す。
    if len(text) <= max_length: 
        return text
    
    # 文字数が上限を超えていた時のみ、トリム後、最終文字を"..."とする文字列を返す。
    truncated_text = text[:max_length - 1] + "…"
    return truncated_text


def get_carousel_info(shop_detail: tuple) -> dict:
    '''
    選ばれた店舗に対して、カルーセル表示用店舗情報の抽出
    対象店舗は extract_introduce_shop_ids() で先に決める。
    '''
    if shop_detail:

        affiliate_url = get_affiliate_url(shop_detail['id']) # affiliate_urlを生成

        # 店舗詳細表示情報の設定。店舗評価が取得できれば後ろにつける。
        shop_rate = get_shop_review(shop_detail['id'])
        if shop_rate:
            detail_message = shop_detail['mobile_access'] + "\n" + shop_rate
        else:
            detail_message = shop_detail['mobile_access']

        carousel_info = {
            'id': shop_detail['id'],
            'name': trim_text(shop_detail['name']),
            'rate':shop_rate,
            'detail_message':detail_message,
            'url': affiliate_url,
            'pic_url': shop_detail['photo']['pc']['l']
        }

        return carousel_info

    # デバッグ用
    else:
        print("Error: cant get CarouselInfo : func get_carousel_info")
        return False


def get_affiliate_url(shop_id):
    '''
    affiliate_urlを作成
    '''
    # shop_id前後につけるおまじない
    url_top = "https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=3690883&pid=889260573&vc_url=https%3A%2F%2Fwww.hotpepper.jp%2Fstr"
    url_bottom = "%2F%3Fvos%3Dnhppvccp99002"
    # アフィURL生成
    affiliate_url = url_top + shop_id + url_bottom

    return affiliate_url


def get_neccessory_carousel_column(query_record):
    '''
    店舗検索結果と同時に表示する定型カルーセル
    とりあえずPoweredByホットペッパーグルメにしてる。
    '''
    neccessory_carousel_column = CarouselColumn(
        thumbnail_image_url="https://document.intra-mart.jp/library/rpa/public/im_rpa_usage_guide/_images/winactor_tutorial_5_4_1.png",
        title="こちらの条件で検索中",
        text= query_record.text_for_carousel(),
        actions=[
            {
                "type": "uri",
                "label": "検索条件を変更する",
                "uri": SEARCH_FORM_LIFF
            },
            {
                "type": "message",
                "label": "次の5件を表示",
                "text": "次の5件"
            }
        ]
    )

    return neccessory_carousel_column


def encode_uri_parameters(shop_id):
    '''
    URIでのパラメータをエスケープするためのUTF-8エンコーダ

    current_shop_params = {
        'pic_url' : carousel_info['pic_url'],
        'title' : carousel_info['name'],
        'review' : carousel_info['detail_message'],
        'affiliate_url' : get_affiliate_url(shop_ids[i]) # js用店舗アフィリンク
    }

    '''

    #共有先でカルーセルを生成するためのクエリ(店舗情報)
    parameters = {
        'shop_id' : shop_id # js用店舗id 文字数削減
    }

    encoded_params = []
    for key, value in parameters.items():
        encoded_key = urllib.parse.quote(key)
        encoded_value = urllib.parse.quote(value)
        encoded_params.append(f"{encoded_key}={encoded_value}")


    encoded_query = "&".join(encoded_params)
    print(encoded_query)
    return encoded_query


def get_shop_ids_by_search_urls(numbering_search_urls: list) -> list:
    """ numbering_seach_urls のURL中のshop_idのリスト。

    Args:
        numbering_search_urls (list[str]): _description_

    Returns:
        list[str]: numbering_seach_urls のURL中のshop_id全てをappendして返す。
    """

    shop_ids = [] # return変数

    # 各ナンバリングURLに含まれる shop_ids をappendしていく。
    for current_numbering_search_url in numbering_search_urls:
        # 各ナンバリングURLに含まれるshop_idsを取得
        current_page_shop_ids = get_shop_ids_by_search_url(current_numbering_search_url)
        # current_shop_id に分けてappend
        for current_shop_id in current_page_shop_ids:
            shop_ids.append(current_shop_id)

    return shop_ids


def get_shop_ids_by_search_url(search_url: str) -> list:
    """検索条件URLでヒットしたshop_idを、MAX_DISPLAY_SHOP_QUANTITY個取得。

    Args:
        search_url (str): ホットペッパーの検索URL。

    Returns:
        list[str]: shop_idのリスト。 ["J001168707", ... ,"J999999999"]
    """


    request = requests.get(search_url) # 検索条件URLでリクエスト
    soup = BeautifulSoup(request.text, 'html.parser') # BSでスクレイピング、リクエスト結果を取得

    html_shop_lists = soup.find_all('h3', class_='shopDetailStoreName') # スクレイピングでヒットした店舗リストを取得(最大でmax_shop_quantity店舗。)

    if not html_shop_lists: # スクレイピングで1店舗もヒットしなかった場合
        return
    
    shop_ids = get_shop_ids_from_html_shop_lists(html_shop_lists) # HTMLの店舗リストから、shop_idを取得

    return shop_ids # ["J001168707", ... ,"J999999999"]


def get_shop_ids_from_html_shop_lists(html_shop_lists):
    '''
    スクレイピングで取得した html_shop_lists から shop_ids を抜きだす。
    '''

    # return変数
    shop_ids = []

    # HTMLの店舗リストから、shop_idを取得
    for html_shop_list in html_shop_lists:
        # html_shop_list から shop_id の抽出
        current_href_shop_id = html_shop_list.find('a')['href']  # "/strJ001168707/"
        current_shop_id = current_href_shop_id[4:len(current_href_shop_id) - 1]  # "J001168707"
        # shop_idsに追加
        shop_ids.append(current_shop_id)

    return shop_ids # ["J001168707", ... ,"J999999999"]


def get_user_id_from_event(event):
    '''
    ユーザーID(グループIDもしくは個人ID）の取得
    '''

    # まずグループか判定→グループidを返す。
    if event.source.type == "group":
        return event.source.group_id
    # グループでなければ個人であるか判定→個人idを返す。
    elif event.source.type == "user":
        return event.source.user_id
    # 取得できない場合はエラー値 -1 を返す。
    else:
        print("error: get_user_id_from_event : cant get id")
        return None


def get_user_index_from_database(user_ids: list, user_id: str) -> int:
    """全体リストに user_id ある場合、SearchQueryと対応するインデックス番号（レコード番号）を返す。
        新規ユーザーについても。前工程で登録しているはずだが、登録できていない場合はNoneを返す。

    Args:
        user_ids (list[str]): user_id のリスト。今までの利用者全てのid。
        user_id (str): メッセージイベントを起こしたユーザーのid。

    Returns:
        int: そのユーザーの、SearchQueryと対応するインデックス番号（レコード番号）を返す。
            未登録のuser_idだった場合は、インデックスがないためNoneを返す。
    """

    # 全体リストに user_id がない場合 Noneを返す
    if user_id not in user_ids:
        print("エラー:新規ユーザーにもかかわらず、append_new_user_to_listでリストに追加できていないようです。")
        return 
    
    # 全体リストに user_id ある場合、インデックス（レコード番号）を返す。
    return user_ids.index(user_id)

def list_subtract(larger_list: list, smaller_list: list) -> list:
    """リストの要素の引き算。

    Args:
        larger_list (list): 引かれる側のリスト
        smaller_list (list): 引く側のリスト

    Returns:
        list: 引き算後のリスト
    """

    return [item for item in larger_list if item not in smaller_list]


if __name__ == "__main__":

    # DBの初期設定
    DATABASE_PATH = 'Database/sqlite_database.db' # DBのパス
    connect = sqlite3.Connection(DATABASE_PATH)
    db.setup_database(DATABASE_PATH)

    # 格納配列の宣言 それぞれインデックスで対応。user_infos[user_id, search_query]とかで統合した方がいい・・？
    search_queries = []
    user_ids = []

    # 検索対象の記号を設定[記号,False:スペースを削除,True:スペースを文字列に含む]
    query_marks = [["/", False], ["+", False], ["¥", False], ["=", True]]

    # グループ参加時のメッセージ設定
    join_message = TutorialMessages.JoinMessage(query_marks)
    # チュートリアル要求時のメッセージ設定
    tutorial_message = TutorialMessages.TutorialMessage()

    # 1回に提案する店舗数の上限
    MAX_DISPLAY_SHOP_QUANTITY = 5
    # 検索結果のうち、ユーザーが保持できるページ数
    MAX_HIT_PAGE_STOCK_QUANTITY = 3

    
    # LINE BOT
    app.run()