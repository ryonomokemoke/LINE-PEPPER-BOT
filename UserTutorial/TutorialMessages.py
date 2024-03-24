# 必要なライブラリのインポート
from linebot.models import FlexSendMessage
from linebot.models.flex_message import BubbleContainer

# グループ参加時のメッセージ
def JoinMessage(criteria_marks):
    join_message = FlexSendMessage(
        alt_text='代替えテキスト',
        contents=BubbleContainer(
            direction='ltr',
            body={
                'type': 'box',
                'layout': 'vertical',
                'contents': [
                    {
                        'type': 'text',
                        'text': '好みの居酒屋を教えてください！',
                        'size': 'lg',
                        'weight': 'bold',
                        'margin': 'none',
                    },
                    {
                        'type': 'text',
                        'text': '日付 ' + criteria_marks[0][0],
                        'size': 'md',
                        # 'margin': 'md',
                    },
                    {
                        'type': 'text',
                        'text': '駅・場所 ' + criteria_marks[1][0],
                        'size': 'md',
                        # 'margin': 'md',
                    },
                    {
                        'type': 'text',
                        'text': '予算 ' + criteria_marks[2][0],
                        'size': 'md',
                        # 'margin': 'md',
                    },
                    {
                        'type': 'text',
                        'text': 'フリーテキスト ' + criteria_marks[3][0],
                        'size': 'md',
                        # 'margin': 'md',
                    },
                    {
                        'type': 'text',
                        'text': '例',
                        'size': 'lg',
                        'weight': 'bold',
                        'margin': 'md',
                    },
                    {
                        'type': 'text',
                        'text':  criteria_marks[0][0] + '20230831',
                        'size': 'md',
                        # 'margin': 'md',
                    },
                    {
                        'type': 'text',
                        'text': criteria_marks[1][0] + '新宿',
                        'size': 'md',
                        # 'margin': 'md',
                    },
                    {
                        'type': 'text',
                        'text': criteria_marks[2][0] + '3500',
                        'size': 'md',
                        # 'margin': 'md',
                    },
                    {
                        'type': 'text',
                        'text': criteria_marks[3][0] + '飲み放題 チーズ',
                        'size': 'md',
                        # 'margin': 'md',
                    },
                    {
                    "type": "button",
                    "style": "secondary",
                    "color": "#74FF84",
                    'margin': 'md',
                    "action": {
                    "type": "message",
                    "label": "チュートリアル表示",
                    "text": "?チュートリアル表示",
                        },
                    },
                ]
            }
        )
    )
    return join_message
    
# チュートリアル要求時のメッセージ
def TutorialMessage():
    tutorial_message = FlexSendMessage(
        alt_text='?チュートリアル表示',
        contents=BubbleContainer(
            direction='ltr',
            body={
                'type': 'box',
                'layout': 'vertical',
                'contents': [
                    {
                        'type': 'text',
                        'text': '使い方',
                        'size': 'lg',
                        'weight': 'bold',
                        'margin': 'none',
                    },
                    {
                    "type": "button",
                    "style": "secondary",
                    "color": "#78C5FF",
                    'margin': 'md',
                    "action": {
                    "type": "message",
                    "label": "お店の見つけ方",
                    "text": "?お店の見つけ方",
                        },
                    },
                    {
                    "type": "button",
                    "style": "secondary",
                    "color": "#78C5FF",
                    'margin': 'md',
                    "action": {
                    "type": "message",
                    "label": "書き方",
                    "text": "?書き方",
                        },
                    },
                    {
                    "type": "button",
                    "style": "secondary",
                    "color": "#FF8189",
                    'margin': 'md',
                    "action": {
                    "type": "message",
                    "label": "Q&A",
                    "text": "?Q&A",
                        },
                    },
                ]
            }
        )
    )
    return tutorial_message

