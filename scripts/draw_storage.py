"""Draw schematic storage collages for the three Cambusa v17 facade directions."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'outputs/cambusa-frame-v17/storage'
OUT.mkdir(parents=True,exist_ok=True)
BG = '#f2eee5'
INK = '#222e2c'
MUTED = '#54615b'
FRAME = '#272b2b'
WOOD = '#78553b'
EDGE = '#ad8562'
BACK = '#62452f'
DEEP = '#4d3628'
PAPER = '#dcd6c1'
GLASS = '#aabfc0'

VARIANTS = [
    ('01-solid','01','Закрытый фотоархив','Показывать коллекцию, когда двери открыты.',
     'Камеры и объективы за двумя глухими створками.',
     'Слайды в архивных коробках. Книги внизу.',
     'Лотки с крышками для деталей клавиатур.'),
    ('02-glass','02','Витрина со шторкой','Показывать пару камер за стеклом.',
     'Окно в правой створке, за ним полка для экспозиции.',
     'Внутренняя глухая вставка закрывает окно.',
     'Плёнка и слайды в тёмной секции.'),
    ('03-books','03','Книги на виду','Книги доступны, фотоаппаратура закрыта.',
     'Верхняя правая ниша открыта для книг.',
     'Камеры в соседней закрытой секции.',
     'Нижняя створка скрывает мелкие коробки.'),
]


def font(size,bold=False):
    mac = Path('/System/Library/Fonts/Supplemental')/('Arial Bold.ttf' if bold else 'Arial.ttf')
    for path in (str(mac),'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(path,size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def rect(d,x,y,w,h,fill,outline=None,width=1):
    d.rectangle((x,y,x+w,y+h),fill=fill,outline=outline,width=width)


def camera(d,x,y,s=1):
    rect(d,x,y+6*s,57*s,29*s,'#222929', '#131b19')
    rect(d,x,y+6*s,57*s,8*s,'#b5b7aa')
    rect(d,x+17*s,y,21*s,8*s,'#b5b7aa')
    rect(d,x+4*s,y+8*s,10*s,4*s,'#37423d')
    d.ellipse((x+17*s,y+10*s,x+42*s,y+34*s),fill='#3c4944',outline='#191d1d',width=2)
    d.ellipse((x+22*s,y+15*s,x+37*s,y+30*s),fill='#657976',outline='#121a17')
    d.ellipse((x+24*s,y+18*s,x+33*s,y+27*s),fill='#273733')


def lens(d,x,y,s=1):
    rect(d,x,y+4*s,25*s,34*s,'#303635')
    for offset in (8,12,19,23,30):
        rect(d,x,y+offset*s,25*s,1*s,'#4e5752')
    d.ellipse((x,y,x+25*s,y+10*s),fill='#171e1c',outline='#77867e')


def boxes(d,x,y,color,word):
    for j in range(2):
        rect(d,x,y+24*j,69,20,color,'#44483e')
        rect(d,x+3,y+24*j,63,3,'#9b9a86')
        rect(d,x+14,y+24*j+7,40,8,PAPER)
        d.text((x+34,y+24*j+11),word,anchor='mm',fill=INK,font=font(7))


def books(d,x,y):
    for j,(w,h,color) in enumerate([
        (11,41,'#9eab8d'),(14,52,'#ae795c'),(10,44,'#d4c28d'),
        (13,55,'#617e7d'),(10,40,'#99695e'),(12,51,'#bda98a'),
    ]):
        rect(d,x,y-h,w,h,color,'#4b493c')
        rect(d,x+2,y-7,w-4,1,PAPER)
        x+=w+2


def keyboard(d,x,y):
    rect(d,x,y,78,43,'#787b67','#3f453a')
    for col in range(6):
        for row in range(3):
            fill = ('#d1c9ab','#839691','#b48e69')[(col+row*2)%3]
            rect(d,x+4+12*col,y+4+12*row,8,8,fill,'#777664')


def elevation(d,x,y,mode,inside):
    w,h=224,224
    # The cabinet body is square in elevation and sits 800 mm above the floor.
    d.ellipse((x-20,y+398,x+w+20,y+414),fill='#ddd7cb')
    rect(d,x,y,w,h,FRAME)
    rect(d,x+1,y+h,7,178,FRAME)
    rect(d,x+w-8,y+h,7,178,FRAME)
    rect(d,x+7,y+h+164,w-14,5,'#393e3c')
    rect(d,x+8,y+8,w-16,h-16,BACK)
    for side in range(2):
        col=x+9+104*side
        if inside:
            rect(d,col,y+8,101,207,DEEP)
            for z in (75,145):
                rect(d,col,y+z,101,5,EDGE)
            if mode == 3:
                camera(d,col+15,y+39,.84) if side==0 else books(d,col+9,y+75)
                if side==0:
                    lens(d,col+67,y+44,.76)
                else:
                    keyboard(d,col+11,y+96)
            else:
                if side==0:
                    boxes(d,col+15,y+25,'#918e76','СЛАЙДЫ')
                else:
                    camera(d,col+10,y+39,.90)
                    lens(d,col+70,y+43,.81)
            if side==0:
                if mode!=3:
                    lens(d,col+18,y+107,.85)
                    lens(d,col+52,y+102,1)
                else:
                    boxes(d,col+14,y+97,'#918e76','СЛАЙДЫ')
                books(d,col+10,y+210)
            else:
                if mode!=3:
                    keyboard(d,col+11,y+96)
                boxes(d,col+15,y+165,'#8f7b63','ДЕТАЛИ')
        else:
            rect(d,col,y+8,101,207,WOOD,EDGE,2)
            rect(d,col+7,y+16,87,191,'#805c40','#63462f')
            rect(d,col+(88 if side==0 else 11),y+111,2,29,FRAME)
            if side==1 and mode in (2,3):
                rect(d,col+6,y+15,89,64,DEEP,EDGE)
                if mode==2:
                    camera(d,col+12,y+38,.9)
                    lens(d,col+67,y+38,.80)
                    d.line((col+18,y+18,col+8,y+30),fill=GLASS,width=2)
                    d.line((col+91,y+20,col+63,y+49),fill=GLASS,width=2)
                    d.line((col+90,y+36,col+81,y+46),fill=GLASS,width=2)
                else:
                    books(d,col+11,y+77)
    if inside:
        rect(d,x+109,y+8,6,207,WOOD)
    for yy in (0,216):
        rect(d,x,y+yy,w,8,FRAME)


def board(config,variant):
    slug,number,title,subtitle,*notes=config
    image=Image.new('RGB',(1400,765),BG)
    d=ImageDraw.Draw(image)
    rect(d,0,0,1400,7,'#73867b')
    d.text((44,32),f'CAMBUSA  /  ХРАНЕНИЕ  /  {number}',font=font(19,True),fill=MUTED)
    d.text((44,63),title,font=font(51,True),fill=INK)
    d.text((46,127),subtitle,font=font(25),fill=MUTED)
    for x,label,opened in ((80,'Фасад',False),(398,'Распределение внутри',True)):
        elevation(d,x,213,variant,opened)
        d.text((x,657),label,font=font(21,True),fill=INK)
    d.line((700,209,700,685),fill='#c8c4b7',width=2)
    for j,note in enumerate(notes):
        y=227+j*112
        rect(d,750,y,9,31,('#82978e','#a28162','#bdae8b')[j])
        words=note.split()
        lines=['']
        for word in words:
            trial=(lines[-1]+' '+word).strip()
            if d.textlength(trial,font=font(27))>538:
                lines.append(word)
            else:
                lines[-1]=trial
        d.multiline_text((775,y-1),'\n'.join(lines),fill=INK,font=font(27),spacing=7)
    d.line((750,579,1343,579),fill='#c8c4b7',width=2)
    d.text((750,602),'Пегборд слева · 100 × 180 × 50 см',fill=MUTED,font=font(22))
    d.text((750,640),'Эскиз · проверим размеры предметов',fill=MUTED,font=font(18))
    image.save(OUT/f'{slug}.png',optimize=True)
    return image


panels=[board(config,variant) for variant,config in enumerate(VARIANTS,1)]
overview=Image.new('RGB',(1260,3*689+24),BG)
for i,image in enumerate(panels):
    preview=image.resize((1260,689),Image.Resampling.LANCZOS)
    overview.paste(preview,(0,i*689+12))
overview.save(OUT/'storage-collages.png',optimize=True)
print('3 storage collages and overview generated')
