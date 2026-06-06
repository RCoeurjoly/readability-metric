"""Tag books from known external/canonical ranking lists."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable


CHINESE_NOVEL_20C_TOP100 = [
    (1, "呐喊", "鲁迅"),
    (2, "边城", "沈从文"),
    (3, "骆驼祥子", "老舍"),
    (4, "传奇", "张爱玲"),
    (5, "围城", "錢鍾書"),
    (6, "子夜", "茅盾"),
    (7, "台北人", "白先勇"),
    (8, "家", "巴金"),
    (9, "呼兰河传", "萧红"),
    (10, "老残游记", "刘鹗"),
    (11, "寒夜", "巴金"),
    (12, "彷徨", "鲁迅"),
    (13, "官场现形记", "李伯元"),
    (14, "财主底儿女们", "路翎"),
    (15, "将军族", "陈映真"),
    (16, "沉沦", "郁达夫"),
    (17, "死水微澜", "李劼人"),
    (18, "红高粱", "莫言"),
    (19, "小二黑结婚", "赵树理"),
    (20, "棋王", "鍾阿城"),
    (21, "家變", "王文兴"),
    (22, "马桥词典", "韩少功"),
    (23, "亚细亚的孤儿", "吴浊流"),
    (24, "半生缘", "张爱玲"),
    (25, "四世同堂", "老舍"),
    (26, "胡雪巖", "高阳"),
    (27, "啼笑因缘", "张恨水"),
    (28, "儿子的大玩偶", "黄春明"),
    (29, "射雕英雄传", "金庸"),
    (30, "莎菲女士的日记", "丁玲"),
    (31, "鹿鼎记", "金庸"),
    (32, "孽海花", "曾朴"),
    (33, "惹事", "赖和"),
    (34, "嫁妆一牛车", "王祯和"),
    (35, "异域", "柏杨"),
    (36, "曾国藩", "唐浩明"),
    (37, "原乡人", "锺理和"),
    (38, "白鹿原", "陈忠实"),
    (39, "长恨歌", "王安忆"),
    (40, "吉陵春秋", "李永平"),
    (41, "黄祸", "王力雄"),
    (42, "狂风沙", "司马中原"),
    (43, "艳阳天", "浩然"),
    (44, "公墓", "穆时英"),
    (45, "旧址", "李锐"),
    (46, "星星·月亮·太阳", "徐速"),
    (47, "台湾人三部曲", "锺肇政"),
    (48, "洗澡", "杨绛"),
    (49, "旋风", "姜贵"),
    (50, "荷花淀", "孙犁"),
    (51, "我城", "西西"),
    (52, "受戒", "汪曾祺"),
    (53, "铁浆", "朱西甯"),
    (54, "世纪末的华丽", "朱天文"),
    (55, "蜀山剑侠传", "还珠楼主"),
    (56, "又见棕榈，又见棕榈", "于梨华"),
    (57, "浮躁", "贾平凹"),
    (58, "组织部新来的年轻人", "王蒙"),
    (59, "玉梨魂", "徐枕亚"),
    (60, "香港三部曲", "施叔青"),
    (61, "京华烟云", "林语堂"),
    (62, "倪焕之", "叶圣陶"),
    (63, "春桃", "许地山"),
    (64, "桑青与桃红", "聂华苓"),
    (65, "蓝与黑", "王蓝"),
    (66, "二月", "柔石"),
    (67, "风萧萧", "徐訏"),
    (68, "芙蓉镇", "古华"),
    (69, "地之子", "臺静農"),
    (70, "城南旧事", "林海音"),
    (71, "古船", "张炜"),
    (72, "酒徒", "刘以鬯"),
    (73, "未央歌", "鹿桥"),
    (74, "沉重的翅膀", "张洁"),
    (75, "果园城记", "师陀"),
    (76, "人啊，人！", "戴厚英"),
    (77, "黄金时代", "王小波"),
    (78, "狗日的粮食", "刘恒"),
    (79, "棋王", "张系国"),
    (80, "赖索", "黄凡"),
    (81, "妻妾成群", "苏童"),
    (82, "霸王别姬", "李碧华"),
    (83, "杀夫", "李昂"),
    (84, "楚留香", "古龙"),
    (85, "窗外", "琼瑶"),
    (86, "沉默之岛", "苏伟贞"),
    (87, "白发魔女传", "梁羽生"),
    (88, "古都", "朱天心"),
    (89, "尹县长", "陈若曦"),
    (90, "四喜忧国", "张大春"),
    (91, "喜寶", "亦舒"),
    (92, "男人的一半是女人", "张贤亮"),
    (93, "将军底头", "施蛰存"),
    (94, "蓝血人", "倪匡"),
    (95, "二十年目睹之怪现状", "吴趼人"),
    (96, "活著", "余华"),
    (97, "冈底斯的诱惑", "马原"),
    (98, "十年十意", "林斤澜"),
    (99, "北极风情画", "无名氏"),
    (100, "雍正皇帝", "二月河"),
]

# Small, explicit variant map for common simplified/traditional differences in the list.
# This is deliberately conservative; ambiguous matches still require exact title+author or unique title.
CHAR_VARIANTS = str.maketrans(
    {
        "呐": "吶", "爱": "愛", "边": "邊", "骆": "駱", "驼": "駝", "祥": "祥", "张": "張",
        "钱": "錢", "钟": "鍾", "书": "書", "兰": "蘭", "萧": "蕭", "残": "殘",
        "刘": "劉", "鹗": "鶚", "场": "場", "现": "現", "记": "記", "将": "將",
        "军": "軍", "陈": "陳", "郁": "郁", "澜": "瀾", "红": "紅", "赵": "趙",
        "树": "樹", "马": "馬", "词": "詞", "韩": "韓", "细": "細", "缘": "緣",
        "阳": "陽", "啼": "啼", "妆": "妝", "异": "異", "国": "國", "藩": "藩",
        "乡": "鄉", "锺": "鍾", "诚": "誠", "长": "長", "旧": "舊", "锐": "銳",
        "星": "星", "湾": "灣", "杨": "楊", "绛": "絳", "孙": "孫", "铁": "鐵",
        "浆": "漿", "华": "華", "侠": "俠", "传": "傳", "还": "還", "见": "見",
        "梨": "梨", "贾": "賈", "凹": "凹", "轻": "輕", "云": "雲",
        "语": "語", "叶": "葉", "圣": "聖", "聂": "聶", "蓝": "藍", "风": "風",
        "镇": "鎮", "静": "靜", "农": "農", "旧": "舊", "张": "張", "洁": "潔",
        "师": "師", "粮": "糧", "苏": "蘇", "杀": "殺", "岛": "島", "县": "縣",
        "忧": "憂", "宝": "寶", "贤": "賢", "蛰": "蟄", "血": "血", "趼": "趼",
        "著": "著", "诱": "誘", "极": "極", "画": "畫", "雍": "雍", "悦": "悅",
    }
)

LIST_ID = "20c_chinese_novel_top100"
LIST_NAME = "20世纪中文小说100强"
SOURCE_URL = "https://zh.wikipedia.org/wiki/20%E4%B8%96%E7%BA%AA%E4%B8%AD%E6%96%87%E5%B0%8F%E8%AF%B4100%E5%BC%BA"


FRENCH_LE_MONDE_100_BOOKS_CENTURY = [
    (1, "L'Étranger", "Albert Camus", 1942),
    (2, "À la recherche du temps perdu", "Marcel Proust", "1913-1927"),
    (3, "Le Procès", "Franz Kafka", 1925),
    (4, "Le Petit Prince", "Antoine de Saint-Exupéry", 1943),
    (5, "La Condition humaine", "André Malraux", 1933),
    (6, "Voyage au bout de la nuit", "Louis-Ferdinand Céline", 1932),
    (7, "Les Raisins de la colère", "John Steinbeck", 1939),
    (8, "Pour qui sonne le glas", "Ernest Hemingway", 1940),
    (9, "Le Grand Meaulnes", "Alain-Fournier", 1913),
    (10, "L'Écume des jours", "Boris Vian", 1947),
    (11, "Le Deuxième Sexe", "Simone de Beauvoir", 1949),
    (12, "En attendant Godot", "Samuel Beckett", 1952),
    (13, "L'Être et le Néant", "Jean-Paul Sartre", 1943),
    (14, "Le Nom de la rose", "Umberto Eco", 1980),
    (15, "L'Archipel du Goulag", "Alexandre Soljenitsyne", 1973),
    (16, "Paroles", "Jacques Prévert", 1946),
    (17, "Alcools", "Guillaume Apollinaire", 1913),
    (18, "Le Lotus bleu", "Hergé", 1936),
    (19, "Le Journal d'Anne Frank", "Anne Frank", 1947),
    (20, "Tristes Tropiques", "Claude Lévi-Strauss", 1955),
    (21, "Le Meilleur des mondes", "Aldous Huxley", 1932),
    (22, "1984", "George Orwell", 1949),
    (23, "Astérix le Gaulois", "René Goscinny et Albert Uderzo", 1959),
    (24, "La Cantatrice chauve", "Eugène Ionesco", 1952),
    (25, "Trois essais sur la théorie sexuelle", "Sigmund Freud", 1905),
    (26, "L'Œuvre au noir", "Marguerite Yourcenar", 1968),
    (27, "Lolita", "Vladimir Nabokov", 1955),
    (28, "Ulysse", "James Joyce", 1922),
    (29, "Le Désert des Tartares", "Dino Buzzati", 1940),
    (30, "Les Faux-monnayeurs", "André Gide", 1925),
    (31, "Le Hussard sur le toit", "Jean Giono", 1951),
    (32, "Belle du Seigneur", "Albert Cohen", 1968),
    (33, "Cent ans de solitude", "Gabriel García Márquez", 1967),
    (34, "Le Bruit et la Fureur", "William Faulkner", 1929),
    (35, "Thérèse Desqueyroux", "François Mauriac", 1927),
    (36, "Zazie dans le métro", "Raymond Queneau", 1959),
    (37, "La Confusion des sentiments", "Stefan Zweig", 1927),
    (38, "Autant en emporte le vent", "Margaret Mitchell", 1936),
    (39, "L'Amant de lady Chatterley", "D. H. Lawrence", 1928),
    (40, "La Montagne magique", "Thomas Mann", 1924),
    (41, "Bonjour tristesse", "Françoise Sagan", 1954),
    (42, "Le Silence de la mer", "Vercors", 1942),
    (43, "La Vie mode d'emploi", "Georges Perec", 1978),
    (44, "Le Chien des Baskerville", "Arthur Conan Doyle", "1901-1902"),
    (45, "Sous le soleil de Satan", "Georges Bernanos", 1926),
    (46, "Gatsby le Magnifique", "Francis Scott Fitzgerald", 1925),
    (47, "La Plaisanterie", "Milan Kundera", 1967),
    (48, "Le Mépris", "Alberto Moravia", 1954),
    (49, "Le Meurtre de Roger Ackroyd", "Agatha Christie", 1926),
    (50, "Nadja", "André Breton", 1928),
    (51, "Aurélien", "Louis Aragon", 1944),
    (52, "Le Soulier de satin", "Paul Claudel", 1929),
    (53, "Six Personnages en quête d'auteur", "Luigi Pirandello", 1921),
    (54, "La Résistible Ascension d'Arturo Ui", "Bertolt Brecht", 1959),
    (55, "Vendredi ou les Limbes du Pacifique", "Michel Tournier", 1967),
    (56, "La Guerre des mondes", "H. G. Wells", 1898),
    (57, "Si c'est un homme", "Primo Levi", 1947),
    (58, "Le Seigneur des anneaux", "J. R. R. Tolkien", "1954-1955"),
    (59, "Les Vrilles de la vigne", "Colette", 1908),
    (60, "Capitale de la douleur", "Paul Éluard", 1926),
    (61, "Martin Eden", "Jack London", 1909),
    (62, "La Ballade de la mer salée", "Hugo Pratt", 1967),
    (63, "Le Degré zéro de l'écriture", "Roland Barthes", 1953),
    (64, "L'Honneur perdu de Katharina Blum", "Heinrich Böll", 1974),
    (65, "Le Rivage des Syrtes", "Julien Gracq", 1951),
    (66, "Les Mots et les Choses", "Michel Foucault", 1966),
    (67, "Sur la route", "Jack Kerouac", 1957),
    (68, "Le Merveilleux Voyage de Nils Holgersson à travers la Suède", "Selma Lagerlöf", "1906-1907"),
    (69, "Une chambre à soi", "Virginia Woolf", 1929),
    (70, "Chroniques martiennes", "Ray Bradbury", 1950),
    (71, "Le Ravissement de Lol V. Stein", "Marguerite Duras", 1964),
    (72, "Le Procès-verbal", "J. M. G. Le Clézio", 1963),
    (73, "Tropismes", "Nathalie Sarraute", 1939),
    (74, "Journal", "Jules Renard", 1925),
    (75, "Lord Jim", "Joseph Conrad", 1900),
    (76, "Écrits", "Jacques Lacan", 1966),
    (77, "Le Théâtre et son double", "Antonin Artaud", 1938),
    (78, "Manhattan Transfer", "John Dos Passos", 1925),
    (79, "Fictions", "Jorge Luis Borges", 1944),
    (80, "Moravagine", "Blaise Cendrars", 1926),
    (81, "Le Général de l'armée morte", "Ismail Kadaré", 1963),
    (82, "Le Choix de Sophie", "William Styron", 1979),
    (83, "Romancero gitano", "Federico García Lorca", 1928),
    (84, "Pietr-le-Letton", "Georges Simenon", 1931),
    (85, "Notre-Dame des Fleurs", "Jean Genet", 1944),
    (86, "L'Homme sans qualités", "Robert Musil", "1930-1932"),
    (87, "Fureur et Mystère", "René Char", 1948),
    (88, "L'Attrape-cœurs", "J. D. Salinger", 1951),
    (89, "Pas d'orchidées pour miss Blandish", "James Hadley Chase", 1939),
    (90, "Blake et Mortimer", "Edgar P. Jacobs", 1950),
    (91, "Les Cahiers de Malte Laurids Brigge", "Rainer Maria Rilke", 1910),
    (92, "La Modification", "Michel Butor", 1957),
    (93, "Les Origines du totalitarisme", "Hannah Arendt", 1951),
    (94, "Le Maître et Marguerite", "Mikhaïl Boulgakov", "1967-1973"),
    (95, "La Crucifixion en rose", "Henry Miller", "1949-1960"),
    (96, "Le Grand Sommeil", "Raymond Chandler", 1939),
    (97, "Amers", "Saint-John Perse", 1957),
    (98, "Gaston Lagaffe", "André Franquin", 1957),
    (99, "Au-dessous du volcan", "Malcolm Lowry", 1947),
    (100, "Les Enfants de minuit", "Salman Rushdie", 1981),
]

FRENCH_FIGARO_HALF_CENTURY_NOVELS = [
    (1, "Fermina Márquez", "Valery Larbaud", 1911),
    (2, "Les dieux ont soif", "Anatole France", 1912),
    (3, "La Colline inspirée", "Maurice Barrès", 1913),
    (4, "Un amour de Swann", "Marcel Proust", 1913),
    (5, "Confession de minuit", "Georges Duhamel", 1920),
    (6, "Silbermann", "Jacques de Lacretelle", 1922),
    (7, "Les Faux-monnayeurs", "André Gide", 1925),
    (8, "Thérèse Desqueyroux", "François Mauriac", 1927),
    (9, "La Condition humaine", "André Malraux", 1933),
    (10, "Journal d'un curé de campagne", "Georges Bernanos", 1936),
    (11, "La Nausée", "Jean-Paul Sartre", 1938),
    (12, "La Douceur de la vie", "Jules Romains", 1939),
]

FRENCH_TELERAMA_IDEAL_LIBRARY = [
    (1, "Le Cabinet des Antiques", "Honoré de Balzac", "grands classiques"),
    (2, "Le Maître et Marguerite", "Mikhaïl Boulgakov", "grands classiques"),
    (3, "Sido", "Colette", "grands classiques"),
    (4, "Crime et châtiment", "Dostoïevski", "grands classiques"),
    (5, "Le Comte de Monte-Cristo", "Alexandre Dumas", "grands classiques"),
    (6, "L'Éducation sentimentale", "Gustave Flaubert", "grands classiques"),
    (7, "Le Sang noir", "Louis Guilloux", "grands classiques"),
    (8, "Les Misérables", "Victor Hugo", "grands classiques"),
    (9, "À rebours", "Joris-Karl Huysmans", "grands classiques"),
    (10, "Les Ambassadeurs", "Henry James", "grands classiques"),
    (11, "Journaux", "Franz Kafka", "grands classiques"),
    (12, "A.O. Barnabooth. Ses œuvres complètes", "Valery Larbaud", "grands classiques"),
    (13, "La Montagne magique", "Thomas Mann", "grands classiques"),
    (14, "Les Nouvelles", "Katherine Mansfield", "grands classiques"),
    (15, "Moby-Dick, ou le Cachalot", "Herman Melville", "grands classiques"),
    (16, "À la recherche du temps perdu", "Marcel Proust", "grands classiques"),
    (17, "Histoire de ma vie", "George Sand", "grands classiques"),
    (18, "Une vie", "Italo Svevo", "grands classiques"),
    (19, "Les Aventures de Tom Sawyer & Aventures de Huckleberry Finn", "Mark Twain", "grands classiques"),
    (20, "Vers le phare", "Virginia Woolf", "grands classiques"),
    (21, "Les Grands Cimetières sous la lune", "Georges Bernanos", "romans français contemporains"),
    (22, "La Peste", "Albert Camus", "romans français contemporains"),
    (23, "Un roman russe", "Emmanuel Carrère", "romans français contemporains"),
    (24, "Aucun de nous ne reviendra", "Charlotte Delbo", "romans français contemporains"),
    (25, "Le Ravissement de Lol V. Stein", "Marguerite Duras", "romans français contemporains"),
    (26, "Ravel", "Jean Échenoz", "romans français contemporains"),
    (27, "Mémoire de fille", "Annie Ernaux", "romans français contemporains"),
    (28, "Un balcon en forêt", "Julien Gracq", "romans français contemporains"),
    (29, "Le Protocole compassionnel", "Hervé Guibert", "romans français contemporains"),
    (30, "La Possibilité d'une île", "Michel Houellebecq", "romans français contemporains"),
    (31, "Lambeaux", "Charles Juliet", "romans français contemporains"),
    (32, "Le Grand Cahier", "Agota Kristof", "romans français contemporains"),
    (33, "La Bâtarde", "Violette Leduc", "romans français contemporains"),
    (34, "Continuer", "Laurent Mauvignier", "romans français contemporains"),
    (35, "Vies minuscules", "Pierre Michon", "romans français contemporains"),
    (36, "Dora Bruder", "Patrick Modiano", "romans français contemporains"),
    (37, "La Vie mode d'emploi", "Georges Perec", "romans français contemporains"),
    (38, "Enfance", "Nathalie Sarraute", "romans français contemporains"),
    (39, "L'Acacia", "Claude Simon", "romans français contemporains"),
    (40, "Mémoires d'Hadrien", "Marguerite Yourcenar", "romans français contemporains"),
    (41, "2666", "Roberto Bolaño", "romans étrangers"),
    (42, "Les Impardonnables", "Cristina Campo", "romans étrangers"),
    (43, "L'Année de la pensée magique", "Joan Didion", "romans étrangers"),
    (44, "Une femme fuyant l'annonce", "David Grossman", "romans étrangers"),
    (45, "Nuée d'oiseaux blancs", "Yasunari Kawabata", "romans étrangers"),
    (46, "Nouvelles", "Clarice Lispector", "romans étrangers"),
    (47, "Exhortation aux crocodiles", "António Lobo Antunes", "romans étrangers"),
    (48, "La Ville des prodiges", "Eduardo Mendoza", "romans étrangers"),
    (49, "Avant le bouleversement du monde", "Claire Messud", "romans étrangers"),
    (50, "Paradis", "Toni Morrison", "romans étrangers"),
    (51, "Chroniques de l'oiseau à ressort", "Haruki Murakami", "romans étrangers"),
    (52, "Ada ou l'Ardeur", "Vladimir Nabokov", "romans étrangers"),
    (53, "Blonde", "Joyce Carol Oates", "romans étrangers"),
    (54, "Mason & Dixon", "Thomas Pynchon", "romans étrangers"),
    (55, "La Tache", "Philip Roth", "romans étrangers"),
    (56, "L'Art de la joie", "Goliarda Sapienza", "romans étrangers"),
    (57, "Le Dieu manchot", "José Saramago", "romans étrangers"),
    (58, "Austerlitz", "W. G. Sebald", "romans étrangers"),
    (59, "L'Archipel du goulag", "Alexandre Soljénitsyne", "romans étrangers"),
    (60, "Le Palais de glace", "Tarjei Vesaas", "romans étrangers"),
    (61, "Apologie pour l'histoire ou Métier d'historien", "Marc Bloch", "essais et histoire"),
    (62, "Les Cloches de la Terre", "Alain Corbin", "essais et histoire"),
    (63, "Histoire des émotions", "Alain Corbin, Jean-Jacques Courtine et Georges Vigarello", "essais et histoire"),
    (64, "Le Temps des cathédrales", "Georges Duby", "essais et histoire"),
    (65, "L'Imaginaire médiéval", "Jacques Le Goff", "essais et histoire"),
    (66, "Varennes. La mort de la royauté", "Mona Ozouf", "essais et histoire"),
    (67, "14-18, retrouver la Guerre", "Stéphane Audoin-Rouzeau et Annette Becker", "essais et histoire"),
    (68, "L'Empire gréco-romain", "Paul Veyne", "essais et histoire"),
    (69, "Talleyrand", "Emmanuel de Waresquiel", "essais et histoire"),
    (70, "Le Siècle des intellectuels", "Michel Winock", "essais et histoire"),
    (71, "Peau noire, masques blancs", "Frantz Fanon", "essais et histoire"),
    (72, "Les Mots, la Mort, les Sorts", "Jeanne Favret-Saada", "essais et histoire"),
    (73, "Fragments d'un discours amoureux", "Roland Barthes", "essais et histoire"),
    (74, "Mémoires. 50 ans de réflexion politique", "Raymond Aron", "essais et histoire"),
    (75, "Nous n'avons jamais été modernes", "Bruno Latour", "essais et histoire"),
    (76, "La Misère du monde", "Pierre Bourdieu", "essais et histoire"),
    (77, "Masculin/Féminin. La pensée de la différence", "Françoise Héritier", "essais et histoire"),
    (78, "Le Silence des bêtes", "Élisabeth de Fontenay", "essais et histoire"),
    (79, "King Kong Théorie", "Virginie Despentes", "essais et histoire"),
    (80, "Le Capital au XXIe siècle", "Thomas Piketty", "essais et histoire"),
    (81, "La Foire aux serpents", "Harry Crews", "polars et science-fiction"),
    (82, "Meurtres pour mémoire", "Didier Daeninckx", "polars et science-fiction"),
    (83, "Anatomie d'un crime", "Elizabeth George", "polars et science-fiction"),
    (84, "Underworld USA", "James Ellroy", "polars et science-fiction"),
    (85, "Cœurs solitaires", "John Harvey", "polars et science-fiction"),
    (86, "Étranges Rivages", "Arnaldur Indridason", "polars et science-fiction"),
    (87, "Prendre les loups pour des chiens", "Hervé Le Corre", "polars et science-fiction"),
    (88, "Un pays à l'aube", "Dennis Lehane", "polars et science-fiction"),
    (89, "La Position du tireur couché", "Jean-Patrick Manchette", "polars et science-fiction"),
    (90, "Les Morts de la Saint-Jean", "Henning Mankell", "polars et science-fiction"),
    (91, "Bondrée", "Andrée A. Michaud", "polars et science-fiction"),
    (92, "Meurtre au comité central", "Manuel Vázquez Montalbán", "polars et science-fiction"),
    (93, "GB 84", "David Peace", "polars et science-fiction"),
    (94, "L'Armée furieuse", "Fred Vargas", "polars et science-fiction"),
    (95, "La Religion", "Tim Willocks", "polars et science-fiction"),
    (96, "Chroniques martiennes", "Ray Bradbury", "polars et science-fiction"),
    (97, "Les Cantos d'Hypérion", "Dan Simmons", "polars et science-fiction"),
    (98, "Le Maître du Haut Château", "Philip K. Dick", "polars et science-fiction"),
    (99, "Frankenstein", "Mary Shelley", "polars et science-fiction"),
    (100, "Kirinyaga", "Mike Resnick", "polars et science-fiction"),
]

FRENCH_RANKING_LISTS = [
    {
        "list_id": "le_monde_fnac_100_books_century",
        "list_name": "Les cent livres du siècle",
        "source_url": "https://fr.wikipedia.org/wiki/Les_cent_livres_du_si%C3%A8cle",
        "entries": FRENCH_LE_MONDE_100_BOOKS_CENTURY,
        "ranked": True,
    },
    {
        "list_id": "figaro_12_best_french_language_novels_1900_1950",
        "list_name": "Grand prix des Meilleurs romans du demi-siècle",
        "source_url": "https://fr.wikipedia.org/wiki/Grand_prix_des_Meilleurs_romans_du_demi-si%C3%A8cle",
        "entries": FRENCH_FIGARO_HALF_CENTURY_NOVELS,
        "ranked": False,
    },
    {
        "list_id": "telerama_ideal_library_100",
        "list_name": "Bibliothèque idéale : les 100 livres préférés de Télérama",
        "source_url": "https://www.telerama.fr/livre/bibliotheque-ideale-les-100-livres-preferes-de-telerama-6658929.php",
        "entries": FRENCH_TELERAMA_IDEAL_LIBRARY,
        "ranked": False,
    },
]


def normalize(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKC", value).strip().translate(CHAR_VARIANTS)
    value = "".join(ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch))
    value = value.replace("œ", "oe").replace("Œ", "OE")
    value = re.sub(r"[\s　《》〈〉·．.。!！?？,，、:：;；()（）\[\]【】\-—_’'\"&]+", "", value)
    return value.casefold()


def canonical_entries() -> list[dict]:
    return [
        {
            "list_id": LIST_ID,
            "list_name": LIST_NAME,
            "source_url": SOURCE_URL,
            "rank": rank,
            "title": title,
            "creator": creator,
            "normalized_title": normalize(title),
            "normalized_creator": normalize(creator),
        }
        for rank, title, creator in CHINESE_NOVEL_20C_TOP100
    ]


def french_canonical_entries() -> list[dict]:
    entries = []
    for ranking in FRENCH_RANKING_LISTS:
        for index, item in enumerate(ranking["entries"], start=1):
            rank, title, creator, *rest = item
            publication_year = None
            category = None
            if rest:
                if isinstance(rest[0], (int, str)) and str(rest[0])[:1].isdigit():
                    publication_year = rest[0]
                    category = rest[1] if len(rest) > 1 else None
                else:
                    category = rest[0]
            entries.append(
                {
                    "list_id": ranking["list_id"],
                    "list_name": ranking["list_name"],
                    "source_url": ranking["source_url"],
                    "rank": int(rank) if ranking.get("ranked", True) else index,
                    "rank_position": int(rank) if ranking.get("ranked", True) else None,
                    "title": title,
                    "creator": creator,
                    "publication_year": publication_year,
                    "category": category,
                    "normalized_title": normalize(title),
                    "normalized_creator": normalize(creator),
                }
            )
    return entries



def list_id_from_filename(filename: str) -> str:
    return Path(filename).stem


def load_ranking_json_entries(json_dir: Path) -> list[dict]:
    entries: list[dict] = []
    for path in sorted(json_dir.glob("*.json")):
        if path.name == "manifest.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        list_id = list_id_from_filename(path.name)
        list_name = data.get("榜单名称") or list_id
        source_url = data.get("URL")
        for index, item in enumerate(data.get("条目", []), start=1):
            title = item.get("书名")
            creator = item.get("作者") or item.get("原作者")
            if not title:
                continue
            rank = item.get("rank_position")
            entries.append(
                {
                    "list_id": list_id,
                    "list_name": list_name,
                    "source_url": source_url,
                    "rank": int(rank) if isinstance(rank, int) else index,
                    "rank_position": rank,
                    "title": title,
                    "creator": creator,
                    "publisher": item.get("出版社"),
                    "publication_year": item.get("出版年"),
                    "note": item.get("简短说明/注释"),
                    "normalized_title": normalize(title),
                    "normalized_creator": normalize(creator),
                }
            )
    return entries


def all_catalog_entries(
    ranking_json_dir: Path | None = None,
    include_top100: bool = True,
    include_french: bool = False,
) -> list[dict]:
    entries = []
    if include_top100:
        entries.extend(canonical_entries())
    if include_french:
        entries.extend(french_canonical_entries())
    if ranking_json_dir:
        entries.extend(load_ranking_json_entries(ranking_json_dir))
    return entries

def load_manifest(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def title_matches(candidate: str, canonical: str) -> bool:
    if not candidate or not canonical:
        return False
    if candidate == canonical:
        return True
    # Many classic works are split into volumes in EPUB corpora. Tag those
    # volumes when the manifest title extends a substantial canonical title.
    return len(canonical) >= 12 and candidate.startswith(canonical)


def match_books(manifest_rows: list[dict], entries: list[dict]) -> list[dict]:
    canonical_title_counts: dict[str, int] = {}
    for entry in entries:
        canonical_title_counts[entry["normalized_title"]] = canonical_title_counts.get(entry["normalized_title"], 0) + 1

    normalized_rows = []
    by_title_creator: dict[tuple[str, str], list[dict]] = {}
    by_title: dict[str, list[dict]] = {}
    for row in manifest_rows:
        title = normalize(row.get("title"))
        creator = normalize(row.get("creator"))
        normalized_rows.append((row, title, creator))
        by_title_creator.setdefault((title, creator), []).append(row)
        by_title.setdefault(title, []).append(row)

    matches = []
    seen: set[tuple[str, str, int]] = set()
    for entry in entries:
        candidates = by_title_creator.get((entry["normalized_title"], entry["normalized_creator"]), [])
        match_type = "title_creator_exact"
        if not candidates:
            candidates = [
                row
                for row, title, creator in normalized_rows
                if creator == entry["normalized_creator"] and title_matches(title, entry["normalized_title"])
            ]
            match_type = "title_creator_prefix"
        if not candidates and canonical_title_counts.get(entry["normalized_title"], 0) == 1:
            title_candidates = by_title.get(entry["normalized_title"], [])
            if len(title_candidates) == 1:
                candidates = title_candidates
                match_type = "unique_title_exact"
        for row in candidates:
            key = (str(row.get("book_id")), str(entry["list_id"]), int(entry["rank"]))
            if key in seen:
                continue
            seen.add(key)
            matches.append(
                {
                    "book_id": row.get("book_id"),
                    "title": row.get("title"),
                    "creator": row.get("creator"),
                    "filename": row.get("filename"),
                    "filepath": row.get("filepath"),
                    "book_dir": row.get("book_dir"),
                    "tags": [
                        {
                            "list_id": entry["list_id"],
                            "list_name": entry["list_name"],
                            "source_url": entry["source_url"],
                            "rank": entry["rank"],
                            "canonical_title": entry["title"],
                            "canonical_creator": entry["creator"],
                            "match_type": match_type,
                            "rank_position": entry.get("rank_position", entry["rank"]),
                            "publisher": entry.get("publisher"),
                            "publication_year": entry.get("publication_year"),
                            "category": entry.get("category"),
                            "note": entry.get("note"),
                        }
                    ],
                }
            )
    matches.sort(key=lambda row: row["tags"][0]["rank"])
    return matches


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def write_catalog(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tag book manifest entries with known external ranking lists.")
    parser.add_argument("--manifest", default="results/zh-books/manifest.jsonl")
    parser.add_argument("--output", default="results/book-tags.jsonl")
    parser.add_argument("--catalog-output", default="results/book-tag-catalog.json")
    parser.add_argument("--ranking-json-dir", help="Directory of ranking JSON files to include")
    parser.add_argument("--no-top100", action="store_true", help="Do not include built-in 20th-century Chinese novel top 100 list")
    parser.add_argument("--include-french", action="store_true", help="Include built-in French ranking lists")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)
    entries = all_catalog_entries(
        Path(args.ranking_json_dir) if args.ranking_json_dir else None,
        include_top100=not args.no_top100,
        include_french=args.include_french,
    )
    rows = load_manifest(Path(args.manifest))
    matches = match_books(rows, entries)
    write_jsonl(Path(args.output), matches)
    write_catalog(Path(args.catalog_output), entries)
    print(f"Wrote {len(matches)} tagged book matches to {args.output}")
    print(f"Wrote canonical list catalog to {args.catalog_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
