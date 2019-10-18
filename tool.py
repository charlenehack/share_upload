import  rsa, config, hashlib, os, time, shutil, logging, piexif, chardet, logging.handlers, cv2
from PIL import Image

def rsaEncrypt(str):
    '''
    rsa加密
    :param str: 要加密的明文
    :return: 加密后的密文，公钥
    '''
    (pubkey, privkey) = rsa.newkeys(512)
    content = str.encode('utf-8')
    crypto = rsa.encrypt(content, pubkey)

    return crypto, privkey

def rsaDecrypt(str, privkey):
    '''
    rsa解密
    :param str: 要解密的密文
    :param privkey: 私钥
    :return: 解密后的明文
    '''
    content = rsa.decrypt(str, privkey)
    con = content.decode('utf-8')

    return con

def logger():
    '''
    日志记录并按天轮转
    '''
    fmt_str = '%(asctime)s %(message)s'
    logging.basicConfig()

    fileshandle = logging.handlers.TimedRotatingFileHandler('logs/upload.log', when='D', interval=1)
    fileshandle.suffix = "%Y-%m-%d"
    fileshandle.setLevel(logging.DEBUG)
    formatter = logging.Formatter(fmt_str)
    fileshandle.setFormatter(formatter)
    logging.getLogger('').addHandler(fileshandle)

def get_file_md5(file):
    '''
    计算文件md5
    '''
    fp = open(file, 'rb')
    content = fp.read()
    fp.close()

    return hashlib.md5(content).hexdigest()

def get_day_folder():
    '''
    获取当前日期目录
    :return: year/date
    '''
    t = time.localtime()
    year = time.strftime('%y', t)
    date = t.tm_yday - 1
    if date < 10:
        date = '00' + str(date)
    elif date < 100:
        date = '0' + str(date)
    else:
        date = str(date)

    return year + '/' + date

def get_thumb(width, height):
    '''
    计算缩略图宽高
    :param width: 原图宽
    :param height: 原图高
    :return: 缩略图宽，缩略图高
    '''
    if width >= height:   # 宽大于高
        thumb_height = int((height * config.THUMB_WIDTH) / width)
        return config.THUMB_WIDTH, thumb_height
    else:   # 高大于宽
        thumb_width = int((width * config.THUMB_HEIGHT) / height)
        return thumb_width, config.THUMB_HEIGHT


def get_preview(width, height):
    '''
    计算预览图宽高
    :param width: 原图宽
    :param height: 原图高
    :return: 预览图宽，预览图高
    '''
    if width >= height:  # 宽大于高
        preview_height = int((height * config.PREVIEW_WIDTH) / width)
        return config.PREVIEW_WIDTH, preview_height
    else: # 高大于宽
        preview_width = int((width * config.PREVIEW_HEIGHT) / height)
        return preview_width, config.PREVIEW_HEIGHT

def gen_preview(path, save_path):
    '''
    生成预览图
    :param path: 原图路径
    :param save_path: 保存路径
    :return: 预览图宽，预览图高
    '''
    ext = path.split('.')[-1]
    if ext in ['jpg', 'JPG']:
        type = 'JPEG'
    else:
        type = ext.upper()
    try:
        img = Image.open(path)
        if img.width > config.PREVIEW_WIDTH or img.height > config.PREVIEW_HEIGHT:
            preview_w, preview_h = get_preview(img.width, img.height)
            preview_img = img.resize((preview_w, preview_h), Image.ANTIALIAS)
            preview_img.save(save_path, type)
            return preview_w, preview_h
    except Exception as e:
        logger().info('预览图生成失败--> %s，error：%s' % (path, e))
    return img.width, img.height   # 不满足预览图生成条件返回原图

def gen_thumb(path, save_path):
    '''
    生成缩略图
    :param path: 原图路径
    :param save_path: 保存路径
    :return: 缩略图宽，缩略图高
    '''
    ext = path.split('.')[-1]
    if ext in ['jpg', 'JPG']:
        type = 'JPEG'
    else:
        type = ext.upper()
    try:
        img = Image.open(path)
        thumb_w, thumb_h = get_thumb(img.width, img.height)
        thumb_img = img.resize((thumb_w, thumb_h), Image.ANTIALIAS)
        thumb_img.save(save_path, type)
        return  thumb_w, thumb_h
    except Exception as e:
        logger().info('缩略图生成失败--> %s，error：%s' % (path, e))

def get_pic_info(file_path, article_id, resource_id=0):
    '''
    根据图片路径生成缩略图、预览图并返回图片信息
    :param file_path: 原图路径
    :param site_id: 网址id
    :param brand: 品牌名
    :param article_id: 文章id
    :param resource_id: 文章资源id
    :return: dic, 预览图保存路径，缩略图保存路径
    '''
    file_name = file_path.split('/')[-1]  # 原图名filename.jpg
    name_cut = file_name.split('.')
    if len(name_cut) > 2:
        file_name_lite = '.'.join(name_cut[0:-1])   # 兼容带.文件名
    else:
        file_name_lite = file_name.split('.')[0]  # 原图名filename
    ext = file_path.split('.')[-1]  # 原图扩展名
    if ext not in ['bmp', 'png', 'gif']:
        piexif.remove(file_path)  # 去原图数字水印
    hd_size = os.path.getsize(file_path)  # 原图文件大小
    hd_md5 = get_file_md5(file_path)  # 原图md5
    date = get_day_folder()
    hd_url = os.path.join(date, hd_md5 + '.' + ext)  # 原图url路径
    img = Image.open(file_path)
    hd_w, hd_h = img.size  # 原图宽高
    type = 'image/{}'.format(img.format).lower()  # 原图文件类型
    preview_path = config.SAVE_PATH_TMP + file_name_lite + '_pre.' + ext  # 预览图保存路径
    preview_w, preview_h = gen_preview(file_path, preview_path)  # 生成预览图
    if os.path.isfile(preview_path):
        preview_size = os.path.getsize(preview_path)  # 预览图文件大小
        preview_md5 = get_file_md5(preview_path)  # 预览图md5
        preview_url = os.path.join(date, preview_md5 + '.' + ext)  # 预览图url路径
    else:  # 不满足预览图生成条件使用原图
        preview_size = hd_size
        preview_md5 = hd_md5
        preview_url = hd_url

    thumb_path = config.SAVE_PATH_TMP + file_name_lite + '_thu.' + ext  # 缩略图保存路径
    thumb_w, thumb_h = gen_thumb(file_path, thumb_path)  # 生成缩略图
    #  thumb_size = os.path.getsize(thumb_path)  # 缩略图文件大小
    thumb_md5 = get_file_md5(thumb_path)  # 缩略图md5
    thumb_url = os.path.join(date, thumb_md5 + '.' + ext)  # 缩略图url路径

    data = {
        'article_id': article_id,
        'items': {
            'preview': {
                'md5': preview_md5,
                'path': preview_url,
                'width': preview_w,
                'height': preview_h,
                'extension': ext,
                'size': preview_size,
                'mime': type
            },
            'thumb': {
                'path': thumb_url
            },
            'hdfile': {
                'md5': hd_md5,
                'path': hd_url,
                'width': hd_w,
                'height': hd_h,
                'extension': ext,
                'size': hd_size,
                'mime': type
            },
        },
        'resource_id': resource_id,
        'pic_name': file_name_lite
    }

    return data, preview_path, thumb_path

def get_pic_atta(file_path):
    '''
    获取主图对应矢量图及keywords信息
    :param file_path: 文件路径
    :return: dict
    '''
    ext = file_path.split('.')[-1]  # 文件扩展名
    file_name = file_path.split('/')[-1]  # 原文件名filename.ext
    date = get_day_folder()
    file_size = os.path.getsize(file_path)  # 原文件大小
    file_md5 = get_file_md5(file_path)  # 原文件md5
    file_url = os.path.join(date, file_md5 + '.' + ext)  # 原文件url路径
    if ext == 'txt':
        with open(file_path, 'rb') as f:
            con = f.read()
            codec = chardet.detect(con)['encoding']
        if not codec:
            codec = 'GBK'
        with open(file_path, encoding=codec) as f:
            keywords = f.read()
        return keywords

    if ext in ['eps', 'ai', 'psd']:
        item =  {
                'md5': file_md5,
                'path': file_url,
                'width': 0,
                'height': 0,
                'extension': ext,
                'size': file_size,
                'mime': ext
                }
        return item

def move_to_upload_folder(hd_path, preview_path, thumb_path, items, *vect_path):
    '''
    移动图片到上传目录
    :param hd_path: 原图路径
    :param preview_path: 预览图路径
    :param thumb_path: 缩略图路径
    :param items:
    '''
    date_dir = os.path.join(config.SAVE_PATH, get_day_folder())

    ## 创建日期目录并修改权限
    if not os.path.exists(date_dir):
        os.makedirs(date_dir)
        os.chmod(date_dir, stat.S_IRWXU + stat.S_IRWXG + stat.S_IRWXO)

    is_exist = items['hdfile']['is_exist']
    if not is_exist:
        move_path = os.path.join(config.SAVE_PATH, items['hdfile']['path'])
        shutil.copy(hd_path, move_path)

    is_exist = items['preview']['is_exist']
    if not is_exist:
        move_path = os.path.join(config.SAVE_PATH, items['preview']['path'])
        shutil.move(preview_path, move_path)

    if vect_path:
        vect_ext = vect_path[0].split('.')[-1]
        is_exist = items[vect_ext]['is_exist']
        if not is_exist:
            move_path = os.path.join(config.SAVE_PATH, items[vect_ext]['path'])
            shutil.copy(vect_path[0], move_path)

    # is_exist = items['thumb']['is_exist']
    # if not is_exist:
    move_path = os.path.join(config.SAVE_PATH, items['thumb']['path'])
    shutil.move(thumb_path, move_path)

def backup(folder_path):
    '''
    备份原文件
    :param folder_path: 需备份文件夹路径
    '''
    date = time.strftime(('%Y-%m-%d'), time.localtime())

    b = folder_path.split('/')
    b.insert(-1, date)
    back_dir = '/'.join(b).replace('work', 'backup')
    shutil.copytree(folder_path, back_dir)

def get_pic_classif(dir_path):
    '''
    将目录内文件进行分类
    :param dir_path: 目录路径
    :return: 带标签文件字典，不带标签文件字典，单个文件列表
    '''
    s_tag = set()  # 存放带标签文件关键字
    s_notag = set()  # 存放不带标签文件关键字
    l = list()  # 存放目录内所有文件
    files_tag = dict()  # 存放根据不带标签关键字匹配的对应文件信息
    files_notag = dict()  # 存放根据不带标签关键字匹配的对应文件信息
    l_single = list()  # 存放无主副图及附加信息的单个文件
    l_line = list()  # 存放带下划线的副图

    [l.append(item) for item in os.listdir(dir_path)]

    ## 分别获取带标签和不带标签字典key
    for file in os.listdir(dir_path):
        if file.startswith('.') or file.endswith('db'):
            continue
        name_cut = file.split('.')
        if len(name_cut) > 2:
            file_lite = '.'.join(name_cut[0:-1])  # 兼容带'.'文件名
        else:
            file_lite = file.split('.')[0]
        if '#' in file_lite:
            s_tag.add(file_lite.split('(')[0])
        else:
            # elif '#' not in file_lite and '_' not in file_lite:
            s_notag.add(file_lite)

    ## 获取带标签字典key对应的value
    for lite in s_tag:
        files_tag[lite] = list()
        for file in l:
            if lite in file:
                ext = file.split('.')[-1]
                if ext in ['jpg', 'png'] and '_' not in file:
                    files_tag[lite].insert(0, file)  # 优先处理主图
                else:
                    files_tag[lite].append(file)

    ## 获取不带标签字典key对应的value
    for lite in s_notag:
        files_notag[lite] = list()
        for file in l:
            if lite in file:
                ext = file.split('.')[-1]
                if ext in ['jpg', 'png']:
                    if file == lite + '.' + ext:
                        files_notag[lite].insert(0, file)  # 优先处理主图
                    elif '_' in file and file.split(lite)[1].startswith('_'):  # 兼容带'_'文件名
                        files_notag[lite].append(file)
                else:
                    files_notag[lite].append(file)

    ## 剔除带标签和不带标签字典中的单文件
    for k in list(files_notag):
        if len(files_notag[k]) == 1:
            l_single.append(files_notag[k][0])
            files_notag.pop(k)  # 剔除单元素

    for k in list(files_tag):
        if len(files_tag[k]) == 1:
            l_single.append(files_tag[k][0])
            files_tag.pop(k)

    ## 获取带标签和不带标签字典中带下划线的副图
    for k in list(files_notag):
        for file in files_notag[k]:
            if '_' in file:
                l_line.append(file)
            if '#' in file:
                files_notag.pop(k)  # 剔除带标签文件

    for k in list(files_tag):
        for file in files_tag[k]:
            if '_' in file:
                l_line.append(file)

    l_after = list(set(l_single).difference(set(l_line)))   # 除去单文件中带下划线的副图


    return files_tag, files_notag, l_after

def get_video_cap(file_path):
    '''
    获取视频指定帧截图
    :param file_path: 视频文件路径
    :return: 截图路径
    '''
    filename = file_path.split('/')[-1].split('.')[0:-1][0]
    img_path = config.SAVE_PATH_TMP + filename + '.jpg'
    vc = cv2.VideoCapture(file_path)
    frame = 800  # 取第几帧截图
    times = 0
    while True:
        times += 1
        res, im = vc.read()
        if times % frame == 0:
            cv2.imwrite(img_path, im)
            break
    vc.release()

    return img_path

def get_video_info(file_path):
    '''
    获取视频信息
    :param file_path: 视频文件路径
    :return: dict
    '''
    import mimetypes
    ext = file_path.split('.')[-1]
    size = os.path.getsize(file_path)
    type = mimetypes.guess_type(file_path)[0]
    date = get_day_folder()
    file_md5 = get_file_md5(file_path)
    file_url = os.path.join(date, file_md5 + '.' + ext)
    item = {
        'md5': file_md5,
        'path': file_url,
        'width': 0,
        'height': 0,
        'extension': ext,
        'size': size,
        'mime': type
    }
    return item