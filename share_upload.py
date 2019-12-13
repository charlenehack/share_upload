import os, requests, json, time, queue, shutil, logging
import tool, config
from watchdog.observers import Observer
from watchdog.events import *
from threading import Thread, current_thread

headers = {'Content-Type': 'application/json'}

class FileEventHandler(FileSystemEventHandler):
    def __init__(self):
        FileSystemEventHandler.__init__(self)

    def on_created(self, event):
        if event.is_directory:
            if len(event.src_path.split('/')) == 6:   # 只监控栏目下的一级目录
                logging.warning("发现目录--> {0}".format(event.src_path))
                q.put(event.src_path)

def handle_main_atta(dir, files, article_id, *key):
    for item in files:
      #  print(item)
        data = dict()   # 存放主图、矢量图及keywords信息
        ### 处理主图及附加信息
        for file in files[item]:
            file_path = os.path.join(dir, file)
            filename, ext = file.split('.')[0:2]
            logging.warning('正在处理--> %s', file_path)
            vect_path = None
            #### 拼接主图、矢量图、keywords传参
            try:
                if ext in ['jpg', 'png', 'JPG', 'PNG'] or '#' in filename and '_' not in filename:
                    m_data, preview_path, thumb_path = tool.get_pic_info(file_path, article_id)
                    hd_path = file_path
                    data.update(m_data)
                if ext == 'txt':
                    keywords = tool.get_pic_atta(file_path)
                    data['keywords'] = keywords
                if ext in ['eps', 'ai', 'psd']:
                    vect_path = file_path
                    items = tool.get_pic_atta(file_path)
                    data['items'][ext] = items
                if key and key[0][0] != 'book':   # 判断是否印花图库栏目
                    data['folder_name'] = key[0][0]
                    data['menu_key'] = key[0][1]
            except Exception as e:
                logging.warning('未能找到主图文件，检查文件是否存在或命名是否规范！--> %s',  item)
        if 'items' not in data:
            continue

        ### 趋势书籍栏目创建版面更多图片
        if key and key[0][0] == 'book':
            data['page_id'] = key[0][1]
            data['group_id'] = key[0][2]
            response = requests.post('http://service.wow-trend.us/api/crawler/picture/create', data=json.dumps(data), headers=headers)  # 获取resource_id
            dic_res = json.loads(response.text)
            if dic_res['status_code'] != 200:
                logging.warning('创建书籍页更多图片失败，code：%s，error：%s' % (dic_res['status_code'], dic_res['message']))
                return 1
            items = json.loads(response.text)['data']['items']
        ### 非趋势书籍栏目创建文章资源
        else:
            response = requests.post('http://service.wow-trend.us/api/crawler/upload-article/resource/create', data=json.dumps(data), headers=headers)  # 获取resource_id
            dic_res = json.loads(response.text)
            if dic_res['status_code'] != 200:
                logging.warning('获取resource_id失败，code：%s，error：%s' % (dic_res['status_code'], dic_res['message']))
                return 1
            items = json.loads(response.text)['data']['items']
        resource_id = dic_res['data']['resource_id']
        if vect_path:  # 判断主图是否存在矢量图
            tool.move_to_upload_folder(hd_path, preview_path, thumb_path, items, vect_path)
        else:
            tool.move_to_upload_folder(hd_path, preview_path, thumb_path, items)
        ### 处理副图
        for file in files[item]:
            if '_' in file:
                file_path = os.path.join(dir, file)
                logging.warning('正在处理--> %s', file_path)
                try:
                    s_data, preview_path, thumb_path = tool.get_pic_info(file_path, article_id, resource_id)
                    response = requests.post('http://service.wow-trend.us/api/crawler/upload-article/resource/create', data=json.dumps(s_data), headers=headers)
                    items = json.loads(response.text)['data']['items']
                    tool.move_to_upload_folder(file_path, preview_path, thumb_path, items)
                except Exception as e:
                    logging.warning('处理副图错误。--> %s', file_path)

def Worker(folder_path):
    menu_key, folder = folder_path.split('/')[4:6]

    #### 处理印花图库栏目
    if menu_key in ['印花图库', '素材库']:
        article_id = 0
        files_tag, files_notag, files = tool.get_pic_classif(folder_path)
        if files_tag:
            handle_main_atta(folder_path, files_tag, article_id, [folder, menu_key])
        if files_notag:
            handle_main_atta(folder_path, files_notag, article_id, [folder, menu_key])
        if files:
            for file in files:
                file_path = os.path.join(folder_path, file)
                logging.warning('正在处理--> %s', file_path)
                try:
                    data, preview_path, thumb_path = tool.get_pic_info(file_path, article_id)
                    data['folder_name'] = folder
                    data['menu_key'] = menu_key
                    response = requests.post('http://service.wow-trend.us/api/crawler/upload-article/resource/create', data=json.dumps(data), headers=headers)
                    dic_res = json.loads(response.text)
                    if dic_res['status_code'] != 200:
                        logging.warning('图片处理失败，code：%s，error：%s' % (dic_res['status_code'], dic_res['message']))
                        return 1
                    items = json.loads(response.text)['data']['items']
                    tool.move_to_upload_folder(file_path, preview_path, thumb_path, items)
                except Exception as e:
                    logging.warning('图片处理错误，文件：%s，error：%s' % (file_path, e))
    #### 处理视频上传栏目
    elif menu_key == '视频上传':
        import mimetypes
        article_id = 0
        cover_img = None
        for file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file)
            type = mimetypes.guess_type(file_path)[0]    # 判断是否为视频文件
            if 'video' in type:
                filename = file.split('.')[0:-1][0]
                exts = ['.jpg', '.JPG', '.png', '.PNG', '.jpeg', '.JPEG']  # 判断是否有对应封面图
                for ext in exts:
                    img = os.path.join(folder_path, filename) + ext
                    if os.path.exists(img):
                        cover_img = img
                if not cover_img:   # 若无封面图从视频截取
                    cover_img = tool.get_video_cap(file_path)
                    if os.path.getsize(cover_img) < 10:
                        logging.warning('截取封面图失败--> %s', file_path)
                        return 1
                logging.warning('正在处理--> %s', file_path)
                try:
                    data, preview_path, thumb_path = tool.get_pic_info(cover_img, article_id)
                    hdfile = tool.get_video_info(file_path)
                    data['items']['hdfile'] = hdfile
                    data['folder_name'] = folder
                    data['menu_key'] = menu_key
                    response = requests.post('http://service.wow-trend.us/api/crawler/upload-article/resource/create', data=json.dumps(data), headers=headers)
                    items = json.loads(response.text)['data']['items']
                    tool.move_to_upload_folder(file_path, preview_path, thumb_path, items)
                except Exception as e:
                    logging.warning('文件处理错误，文件：%s，error：%s' % (file_path, e))
    else:
        #### 非印花图库栏目创建文章
        data1 = {
            'folder_name': folder,
            'menu_key': menu_key
        }
        response1 = requests.post('http://service.wow-trend.us/api/crawler/upload-article/create', data=json.dumps(data1), headers=headers)  # 获取article_id
        dic_res1 = json.loads(response1.text)
        if dic_res1['status_code'] != 200:
            logging.warning('获取article_id错误，code：%s，error：%s' % (dic_res1['status_code'], dic_res1['message']))
            return 1
        article_id = dic_res1['data']['article_id']

        #### 处理趋势书籍栏目
        if menu_key == '趋势书籍':
            for folder_name in os.listdir(folder_path):
                if folder_name.startswith('.') or folder_name.endswith('db') or folder_name.endswith('ini'):
                    continue
             #   print(folder_name)
                data = {
                    'folder_name': folder_name,
                    'article_id': article_id,
                    'menu_key': menu_key
                }
                response = requests.post('http://service.wow-trend.us/api/crawler/group/create', data=json.dumps(data), headers=headers)  # 获取group_id
                dic_res = json.loads(response.text)
                if dic_res['status_code'] != 200:
                    logging.warning('获取group_id错误，code：%s，error：%s' % (dic_res['status_code'], dic_res['message']))
                    return 1
                group_id = dic_res['data']['group_id']
                article_id = dic_res['data']['article_id']
                page_id = dic_res['data']['page_id']
                dir = os.path.join(folder_path, folder_name)
                for item in os.listdir(dir):
                    file_path = os.path.join(dir, item)
                    if item.startswith('.') or item.endswith('db') or item.endswith('ini'):
                        os.remove(file_path)
                        continue
                    ## 创建版面
                    if os.path.isfile(file_path):
                        logging.warning('正在处理--> %s', file_path)
                        m_data, preview_path, thumb_path = tool.get_pic_info(file_path, article_id)
                        m_data['group_id'] = group_id
                        m_data['page_id'] = page_id
                        more_dir = m_data['pic_name']
                        response2 = requests.post('http://service.wow-trend.us/api/crawler/page/create', data=json.dumps(m_data), headers=headers)   # 获取版面id
                        dic_res2 = json.loads(response2.text)
                        if dic_res2['status_code'] != 200:
                            logging.warning('获取版面id失败，code：%s，error：%s' % (dic_res2['status_code'], dic_res2['message']))
                            return 1
                        items = json.loads(response2.text)['data']['items']
                        tool.move_to_upload_folder(file_path, preview_path, thumb_path, items)
                        page_id_sub = dic_res2['data']['page_id']
                        more_dir_path = os.path.join(dir, more_dir)
                        ## 处理版面目录更多图片
                        if not os.path.exists(more_dir_path):
                            continue
                        files_tag, files_notag, files = tool.get_pic_classif(more_dir_path)
                      #  print(files_tag, files_notag, files)
                        if files_tag:
                            handle_main_atta(more_dir_path, files_tag, article_id, ['book', page_id_sub, group_id])
                        if files_notag:
                            handle_main_atta(more_dir_path, files_notag, article_id, ['book', page_id_sub, group_id])
                        if files:
                            for more_file in files:
                                more_file_path = os.path.join(more_dir_path, more_file)
                                logging.warning('正在处理--> %s', more_file_path)
                                if more_file.startswith('.') or more_file.endswith('db') or more_file.endswith('ini'):
                                    os.remove(more_file_path)
                                    continue
                                try:
                                    data, preview_path, thumb_path = tool.get_pic_info(more_file_path, article_id)
                                    data['page_id'] = page_id_sub
                                    data['group_id'] = group_id
                                    response3 = requests.post('http://service.wow-trend.us/api/crawler/picture/create', data=json.dumps(data), headers=headers)
                                    dic_res3 = json.loads(response3.text)
                                    if dic_res3['status_code'] != 200:
                                        logging.warning('创建书籍页更多图片失败，code：%s，error：%s' % (dic_res3['status_code'], dic_res3['message']))
                                        return 1
                                    items = json.loads(response3.text)['data']['items']
                                    tool.move_to_upload_folder(more_file_path, preview_path, thumb_path, items)
                                except Exception as e:
                                    logging.warning('图片处理失败-->%s，error：%s' % (file_path, e))

        #### 处理印花图库、趋势书籍之外的其它栏目
        else:
            # 判断图片集或分析类型
            is_dir = False
            for path, dirs, files in os.walk(folder_path):
                for dir in dirs:
                    is_dir = os.path.join(path, dir)
            ### 处理分析类型
            if is_dir:
                for folder_name in os.listdir(folder_path):
                    if folder_name.startswith('.') or os.path.isfile(os.path.join(folder_path, folder_name)):   # 跳过非目录
                        continue
                    data = {
                        'folder_name': folder_name,
                        'article_id': article_id,
                        'menu_key': menu_key
                    }
                    response = requests.post('http://service.wow-trend.us/api/crawler/group/create', data=json.dumps(data), headers=headers)  # 获取group_id
                    dic_res = json.loads(response.text)
                    if dic_res['status_code'] != 200:
                        logging.warning('获取group_id错误，code：%s，error：%s' % (dic_res['status_code'], dic_res['message']))
                        return 1
                    group_id = dic_res['data']['group_id']
                    article_id = dic_res['data']['article_id']
                    dir = os.path.join(folder_path, folder_name)
                    files_tag, files_notag, files = tool.get_pic_classif(dir)
                    if files_tag:
                        handle_main_atta(dir, files_tag, article_id)
                    if files_notag:
                        handle_main_atta(dir, files_notag, article_id)
                    if files:
                        for file in files:
                            file_path = os.path.join(dir, file)
                            logging.warning('正在处理--> %s', file_path)
                            if file.startswith('.') or file.endswith('db') or file.endswith('ini'):
                                os.remove(file_path)
                                continue
                            if not os.path.isfile(file_path):
                                continue
                            try:
                                data, preview_path, thumb_path = tool.get_pic_info(file_path, article_id)
                                data['group_id'] = group_id
                                response = requests.post('http://service.wow-trend.us/api/crawler/upload-article/resource/create', data=json.dumps(data), headers=headers)
                              #  print(response.text)
                                items = json.loads(response.text)['data']['items']
                                tool.move_to_upload_folder(file_path, preview_path, thumb_path, items)
                            except Exception as e:
                                logging.warning('图片处理失败-->%s，error：%s' % (file_path, e))
            ### 处理图片集
            else:
                files_tag, files_notag, files = tool.get_pic_classif(folder_path)
                if files_tag:
                    handle_main_atta(folder_path, files_tag, article_id)
                if files_notag:
                    handle_main_atta(folder_path, files_notag, article_id)
                if files:
                    for file in files:
                        file_path = os.path.join(folder_path, file)
                        logging.warning('正在处理--> %s', file_path)
                        try:
                            data, preview_path, thumb_path = tool.get_pic_info(file_path, article_id)
                            response = requests.post('http://service.wow-trend.us/api/crawler/upload-article/resource/create', data=json.dumps(data), headers=headers)
                            items = json.loads(response.text)['data']['items']
                            tool.move_to_upload_folder(file_path, preview_path, thumb_path, items)
                        except Exception as e:
                            logging.warning('图片处理错误，文件：%s，error：%s' % (file_path, e))

def InitScan():
    for path, dirs, files in os.walk(config.MON_FOLDER):
        for dir in dirs:
            dir_path = os.path.join(path, dir)
            if len(dir_path.split('/')) == 6:
                logging.warning('发现目录--> %s', dir_path)
                q.put(dir_path)

def get_task_stats(folder_path):
    t = 0
    while t < 300:   # 目录超过几长时间没有修改认为写入完成
        try:
            mtime = os.path.getmtime(folder_path)
            t = int(time.time()) - int(mtime)
      #      print(mtime, time.time())
            time.sleep(60)
        except FileNotFoundError:
            logging.warning('目录已被移除--> %s', folder_path)
            return 1
    tname = current_thread().name
    logging.warning('线程：%s，开始处理--> %s' % (tname, folder_path))
    status = Worker(folder_path)
    if not status:
        logging.warning('正在备份目录--> %s', folder_path)
        try:
            tool.backup(folder_path)
            shutil.rmtree(folder_path)
        except Exception as e:
            logging.warning('备份或移除目录错误--> %s，error：%s' % (folder_path, e))
            if 'already exists' in str(e):
                logging.warning('备份目录已存在--> %s', folder_path)
                shutil.rmtree(folder_path)
        finally:
            logging.warning('目录处理完成--> %s', folder_path)
    else:
        logging.warning('目录处理错误--> %s', folder_path)

def run(q):
    while True:
        folder_path = q.get()
        logging.warning('开始追踪目录状态--> %s', folder_path)
        get_task_stats(folder_path)

tool.logger()  # 调用日志处理对象
q = queue.Queue()
observer = Observer()
event_handler = FileEventHandler()
observer.schedule(event_handler, config.MON_FOLDER, True)
observer.start()

for i in range(3):   # 线程数
    p = Thread(target=run, args=(q,))
    p.start()

InitScan()  # 初始化扫描
observer.join()
