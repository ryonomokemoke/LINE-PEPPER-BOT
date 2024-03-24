from linebot.models import TextSendMessage # 必要なライブラリのインポート

import re # 正規表現を扱う
import unicodedata # 記号全般に対応したライブラリ
import jaconv # 全角→半角変換ライブラリ(¥は対応してない)


def calculate_budget_from_text(user_input_price_string, grade_range):
    '''
    与えられた金額user_input_price_string(intにキャスト)を含む、
    合計grade_range個の金額幅となる金額の下限・上限を返す。
    
    ex) user_input_price_string = 3500, grade_range=2
        → 2001, 5000
    '''
    max = [500, 1000, 1500, 2000, 3000, 4000, 5000, 7000, 10000, 15000, 20000, 30000]
    min = [1, 501, 1001, 1501, 2001, 3001, 4001, 5001, 7001, 10001, 15001, 20001]

    user_input_price_int = int(user_input_price_string) # user_input_price(半角変換済み、文字列型)をint型に変換。
    
    if user_input_price_int < min[0]: # 設定できる最低金額以下が入力された場合
        print("error : " + min[0] + "円以上の金額を指定してください。")
        return False, False

    if user_input_price_int >= max[len(max)-1]: # 設定できる最高金額以上が入力された場合
        print("error : " + max[len(max)-1] + "円以下の金額を指定してください。")
        return False, False
    
    budget_max = None
    for i in range(len(max)):
        if max[i] > user_input_price_int:
            budget_max = max[i]
            break
    
    budget_min = None
    # indexの最大値 len(min)-1 から、-1の手前(=0)まで、indexを-1していく。
    for i in range(len(min)-1, -1, -1):
        # user_input_price_intを下回る最大：min[i]
        if min[i] <= user_input_price_int:
            # indexが0以上なら
            if i-grade_range >= 0:
                budget_min = min[i-grade_range]
            # indexがマイナスになってしまったら、min[0]を出力。
            else:
                budget_min = min[0]
                
            # ifがヒットしたらfor文を終了。
            break
            
    return str(budget_min), str(budget_max)


def get_sorted_mark_positions(standardized_text, query_marks):
    '''
    query_marks = [["#",0], ["@",0], ["¥",0], ["*",1]] が含まれている文字の位置と、スペースを含むかを取得(記号の区別なし)
    standardized_text:"*ワイン¥
    return:[[-1, 0], [1, 1], [5, 0], [8, 0]]
    '''
    mark_positions = {} # returnに使う変数

    for query_mark, include_space_flag in query_marks:
        # standardized_textにquery_markが含まれる場合。("clear"を含む。)
        if query_mark in standardized_text:
            # 該当するインデックス番号を出力。
            mark_positions[query_mark] = [standardized_text.index(query_mark), include_space_flag]
        
        # query_markが含まれない場合。
        else:
            mark_positions[query_mark] = [-1, include_space_flag] # mark_positionがない場合は、記号位置を-1で返す。
    
    # ソートのため、辞書型をリスト型に変換
    mark_positions = list(mark_positions.values())  # {'#': [5, 0], '@': [-1, 0], '¥': [8, 0], '*': [1, 1]}
    # 記号位置を小さい順にソート。(include_space_flagも合わせてソート)
    mark_positions.sort() # [[-1, 0], [1, 1], [5, 0], [8, 0]]
    
    return mark_positions


def extract_query_text_until_return(text):
    '''
    概要；最初の改行までの文字列を取り出す。
        textに改行文字が含まれる場合、1文字目〜最初の改行文字 を返す。
        textに改行文字が含まれない場合、そのままtextを返す。
    '''
    for i, char in enumerate(text):
        if char == '\n':
            return text[:i]
    return text
    

def extract_query_text_until_space_or_return(text):
    '''
    最初の改行or空白までの文字列を取り出す。
        textに改行文字もしくは空白文字が含まれる場合、1文字目〜最初の改行or空白文字 を返す。
        textに改行or空白文字が含まれない場合、そのままtextを返す。
    '''
    for i, char in enumerate(text):
        if char == ' ' or char == '\n':
            return text[:i]
    return text
    

def extract_query_text_for_search(seperated_query_text, include_space_flag):
    '''
    概要；入力された１つの検索条件文字列について、スペースや改行までの文字列を取り出す。

    seperated_query_text: （検索条件記号で挟まれた）1つの文字列
    include_space_flag: seperated_query_text 
    
    例)
    seperated_query_text = "新橋　有楽町" → extract_query_text = "新橋" : include_spaace_flag = Flaseの場合
    seperated_query_text = "ワイン　ステーキ  " → extract_query_text = "ワイン ステーキ" : include_spaace_flag = Trueの場合
    '''

    # 検索条件が入力されていなかった場合
    if seperated_query_text == "":
        # 条件クリアのための値を代入(例："# "　→　#の条件をクリア)
        return "(clear)"

    # スペースを含んでいい文字列の場合。
    if include_space_flag == True:
        # 改行のみを取り除く
        extract_query_text = extract_query_text_until_return(seperated_query_text)
    else:
        # スペースと改行を取り除く
        extract_query_text = extract_query_text_until_space_or_return(seperated_query_text)

    return extract_query_text
    

def separate_each_query_text_at_mark(standardized_text, sorted_mark_positions, query_marks):
    '''
    standardized_textをmark_positionsごとに区切って抜き出す。
    ユーザーのキーボード入力に対しての使用を想定。
    query_marksの順番で文字列から検索するため、ユーザーの記号入力順序に関係なく対応。
    
    sorted_mark_positions = [[-1, 0], [1, 1], [5, 0], [8, 0]]
        → [query_mark(種類不問)の文字位置(昇順), spaceをどう扱うかのフラグ]
    '''
    separated_query_texts = [] # returnの入れ物
    last_positon_in_query_text = len(standardized_text) # standardized_textの文末が何文字目か。

    # 各query_marksに対してループを回す。：query_marks = [["/", False], ["+", False], ["¥", False], ["=", True]]
    # appendはquery_marks順に行われる。
    for mark_appearance_order in range(len(query_marks)):
        
        if sorted_mark_positions[mark_appearance_order][0] == -1: # 文章中にない記号を、はじめに処理しきる。
            
            separated_query_texts.append('') # 後工程では、条件クリアではなく、検測条件の維持をする。 
        
        else: # 対象の記号が文章にあったとき(記号位置が正)

            # 検索条件抜き出しの終了位置を取得
            current_query_end_position = get_current_query_end_position(mark_appearance_order, sorted_mark_positions, last_positon_in_query_text)
            # 検索条件の抜き出し
            separated_text = standardized_text[sorted_mark_positions[mark_appearance_order][0]+1:current_query_end_position]
            # 検索条件文の標準化。(改行文字やスペースの削除。ただし、sorted_mark_positions[i][1] (= include_space_flag) == Flaseなら、スペースを残す。)
            current_include_space_flag = sorted_mark_positions[mark_appearance_order][1]
            current_query_text = extract_query_text_for_search(separated_text, current_include_space_flag)
            
            # 今回の記号に対応する検索条件文を、検索条件集に追加。
            separated_query_texts.append(current_query_text)

    return separated_query_texts #['', '新橋', '2500', '海鮮 個室']


def get_current_query_end_position(current_mark_index, sorted_mark_positions, last_positon_in_query_text):
    '''
    current_mark_index個目の条件の、末尾位置を返す。
    '''
    query_mark_quantity = len(sorted_mark_positions) #　検索記号の総数。[/,+,¥,=]なら4。

    if current_mark_index == query_mark_quantity - 1: # 文章中の最後の記号の場合
 
        # 文末をquery_end_positionとする。
        end_position = last_positon_in_query_text
    
    else: # 文章中の最後の記号でない場合

        # 次の記号位置をquery_end_positionとする。
        end_position = sorted_mark_positions[current_mark_index+1][0]

    return end_position # 位置が+1となっているが、のちの処理で綺麗に処理できる。


def sort_queries(standardiized_text, sorted_mark_positions, query_marks, queries):
    '''
    sorted_mark_positionsの記号を返す(?)
    '''
    sorted_queries = ["","","",""]
    for i in range(len(sorted_mark_positions)):
        
        if sorted_mark_positions[i][0] == None:
            continue

        mark = standardiized_text[sorted_mark_positions[i][0]] #mark: i番目の記号
        # sorted_query[j]
        # j=0:"#"に対応する条件, j=1:"@"に対応する条件, j=2:"¥"に対応する条件, j=3:"*"に対応する条件
        for j, query_mark in enumerate(query_marks):
            if mark == query_mark[0]:
                sorted_queries[j] = queries[i]
                break

    return sorted_queries


def split_to_each_query_texts(standardized_text, query_marks):
    '''
    standardized_textから、query_marksに対応して、マーク間の条件を取得する。
    「#+新橋=海鮮 個室」 →  ['(clear)', '新橋', '', '海鮮 個室']
    '''
    # standardized_text : @新橋 富士山 #\n *海鮮 個室
    # 記号位置を取得、小さい順位ソート（standardized_textに含まれていない記号は位置：-1と扱う。）
    sorted_mark_positions = get_sorted_mark_positions(standardized_text, query_marks)

    # 記号位置ごとに文章を分割, スペースや改行の適宜無視も行う。
    queries = separate_each_query_text_at_mark(standardized_text, sorted_mark_positions, query_marks)
    print(f'quaries:{queries}')
    # 記号位置ごとに記号を取得
    sorted_queries = sort_queries(standardized_text, sorted_mark_positions, query_marks, queries)
    
    return sorted_queries # sorted_queries : ['(clear)', '新橋', '', '海鮮 個室']


def has_query_marks(text, query_marks):
    '''
    textにquery_marksが含まるか判定。含まれればTrue。
    '''
    for mark, _ in query_marks:
        if mark in text:
            return True
    return False


def convert_to_half_width(text):
    '''
    与えらえれた文字列の各文字を半角に変換する。（漢字以外）
    '''
    converted_text = ""
    # "¥"のみこちらで変換
    for char in text:
        if char in ["＼", "\\", "￥"]:
            char = "¥"
        # "¥"以外を変換
        char = unicodedata.normalize("NFKC", char)
        converted_text += char
    # その他の記号、スペース、数字など変換
    converted_text = jaconv.z2h(converted_text, digit=True, ascii=True, kana=False)
    
    return converted_text


def standardize_message(text: str):
    '''
    与えられた文字列を以下に沿って整形する。
    ・改行を削除
    ・各文字を半角に変換（漢字以外）
    '''
    text = text.replace("\n","") # 改行を削除
    standardized_message = convert_to_half_width(text) # (おそらく)すべての文字を全角→半角変換
    
    return standardized_message



class UserQuery:

    HOTPEPPER_SEARCH_BASE_URL = "https://www.hotpepper.jp/CSP/psh010/doBasic?"
    PREFECTURE = "SA=SA11"

    def __init__(self, user_query_list):
        self.date = user_query_list[1]
        self.place = user_query_list[2]
        self.price = user_query_list[3]
        self.freeword = user_query_list[4]

    def initialize_query_url(self):
        hotpepper_search_url_date = ""
        hotpepper_search_url_price = ""
        hotpepper_search_url_location_and_freeword = ""

        if self.date:
            hotpepper_search_url_date = "&RDT=" + self.date
        if self.price:
            hotpepper_search_url_price = "&CBT=" + str(self.price)
        
        if self.place and self.freeword:   
            hotpepper_search_url_location_and_freeword = "&FWT=" + self.place + "+" + self.freeword
        elif self.place:
            hotpepper_search_url_location_and_freeword = "&FWT=" + self.place
        elif self.freeword:
            hotpepper_search_url_location_and_freeword = "&FWT=" + self.freeword

        return {
            "date_query": hotpepper_search_url_date,
            "price_query": hotpepper_search_url_price,
            "location_and_freeword_query": hotpepper_search_url_location_and_freeword
        }
    
    def hotpepper_search_url(self):

        query_url = self.initialize_query_url()
        hotpepper_search_url = self.HOTPEPPER_SEARCH_BASE_URL \
                                + "&" + self.PREFECTURE \
                                + "&" + query_url["date_query"] \
                                + "&" + query_url["price_query"] \
                                + "&" + query_url["location_and_freeword_query"]

        return hotpepper_search_url

