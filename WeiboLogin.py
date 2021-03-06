# 微博模拟登录
# 作者: David
# Github: https://github.com/HEUDavid/WeiboSpider

from urllib.parse import quote_plus
import base64
import requests
import time
import rsa
import binascii
import random
import re
import json


class WeiboLogin:

    def __init__(self, username, password):
        self.username = username
        self.password = password

        self.Session = requests.Session()
        self.Session.headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36'}

    def get_su(self):
        '''
        对应 prelogin.php
        对 账号 先 javascript 中 encodeURIComponent
        对应 Python3 中的是 urllib.parse.quote_plus
        然后在 base64 加密后 decode
        '''
        username_quote = quote_plus(self.username)
        username_base64 = base64.b64encode(username_quote.encode('utf-8'))
        su = username_base64.decode('utf-8')
        print('处理后的账户:', su)
        return su

    def get_server_data(self, su):
        '''
        预登陆获得 servertime, nonce, pubkey, rsakv
        '''
        url_str1 = 'https://login.sina.com.cn/sso/prelogin.php?entry=weibo&callback=sinaSSOController.preloginCallBack&su='
        url_str2 = '&rsakt=mod&checkpin=1&client=ssologin.js(v1.4.19)&_='
        pre_url = url_str1 + su + url_str2 + str(int(time.time() * 1000))
        pre_data_res = self.Session.get(pre_url)
        sever_data = eval(pre_data_res.content.decode(
            'utf-8').replace('sinaSSOController.preloginCallBack', ''))
        print('sever_data:', sever_data)
        return sever_data

    def get_password(self, servertime, nonce, pubkey):
        '''
        对密码进行 rsa 加密
        '''
        rsaPublickey = int(pubkey, 16)  # 16进制 string 转化为 int
        key = rsa.PublicKey(rsaPublickey, 65537)  # 创建公钥
        message = str(servertime) + '\t' + nonce + '\n' + self.password
        message = message.encode('utf-8')
        passwd = rsa.encrypt(message, key)  # 加密
        passwd = binascii.b2a_hex(passwd)  # 将加密信息转换为16进制
        print('处理后的密码:', passwd)
        return passwd

    def get_png(self, pcid):
        '''
        获取验证码, 如何识别验证码? 接入打码平台
        有的账号一直不需要验证码?
        '''
        url = 'https://login.sina.com.cn/cgi/pin.php?r='
        png_url = url + str(int(random.random() * 100000000)
                            ) + '&s=0&p=' + pcid
        png_page = self.Session.get(png_url)
        with open('pin.png', 'wb') as f:
            f.write(png_page.content)
            f.close()
            print('验证码下载成功, 请到目录下查看')
        verification_code = input('请输入验证码:')
        return verification_code

    def get_cookie(self):
        su = self.get_su()
        server_data = self.get_server_data(su)
        passwd = self.get_password(
            server_data['servertime'],
            server_data['nonce'],
            server_data['pubkey'])

        # login.php?client=ssologin.js(v1.4.19) 找到 POST 的表单数据
        Form_Data = {
            'entry': 'weibo',
            'gateway': '1',
            'from': '',
            'savestate': '0',
            'useticket': '1',
            'pagerefer': 'https://passport.weibo.com',
            'vsnf': '1',
            'su': su,  # 处理后的账号, 如 MTg4NDY0MjY3NDI=
            'service': 'miniblog',
            'servertime': server_data['servertime'],  # 如 1555504878
            'nonce': server_data['nonce'],  # 如 JU713C
            'pwencode': 'rsa2',
            'rsakv': server_data['rsakv'],  # 如 1330428213
            'sp': passwd,  # 处理后的密码
            'sr': '1366*768',
            'encoding': 'UTF-8',
            'prelt': '243',
            'url': 'https://weibo.com/ajaxlogin.php?framelogin=1&callback=parent.sinaSSOController.feedBackUrlCallBack',
            'returntype': 'TEXT'  # 这里是 TEXT, META 不可以
        }

        login_url = 'https://login.sina.com.cn/sso/login.php?client=ssologin.js(v1.4.19)&_'
        login_url = login_url + str(time.time() * 1000)

        # 有的账号不需要验证码就可以登录
        try:
            # 不输入验证码
            login_page = self.Session.post(login_url, data=Form_Data)
            ticket_js = login_page.json()
        except Exception as e:
            # 输入验证码
            Form_Data['door'] = self.get_png(server_data['pcid'])
            login_page = self.Session.post(login_url, data=Form_Data)
            ticket_js = login_page.json()

        print('昵称:', ticket_js['nick'])
        print('用户uid:', ticket_js['uid'])

        ticket = ticket_js['ticket']
        ssosavestate = ticket.split('-')[2]
        # 处理跳转
        jump_ticket_params = {
            'callback': 'sinaSSOController.callbackLoginStatus',
            'ticket': ticket,
            'ssosavestate': ssosavestate,
            'client': 'ssologin.js(v1.4.19)',
            '_': str(time.time() * 1000),
        }
        jump_url = 'https://passport.weibo.com/wbsso/login'

        jump_login = self.Session.get(jump_url, params=jump_ticket_params)
        jump_login_data = json.loads(
            re.search(r'{.*}', jump_login.text).group(0))
        print('登录状态:', jump_login_data)
        if not jump_login_data['result']:
            # 登录失败 退出
            return None

        # PC 版 个人主页
        weibo_com_home = 'https://weibo.com/u/' + \
            jump_login_data['userinfo']['uniqueid']
        weibo_com_home_page = self.Session.get(weibo_com_home)
        # print('weibo_com_home_page.cookies', weibo_com_home_page.cookies)
        # print(weibo_com_home_page.text[:1500:])
        weibo_com_home_title_pat = r'<title>(.*)</title>'
        weibo_com_home_title = re.findall(
            weibo_com_home_title_pat,
            weibo_com_home_page.text)[0]
        print('PC 版个人主页:', weibo_com_home_title)  # PC 版登录成功

        # PC 版 首页
        weibo_com = 'https://weibo.com'
        weibo_com_page = self.Session.get(weibo_com)
        # print('weibo_com_page.cookies', weibo_com_page.cookies)
        # print(weibo_com_page.text[:1500:])

        # PC 版 搜索页
        s_weibo_com = 'https://s.weibo.com'
        s_weibo_com_page = self.Session.get(s_weibo_com)

        # 触屏版 m.weibo.com
        _rand = str(time.time())
        mParams = {
            'url': 'https://m.weibo.cn/',
            '_rand': _rand,
            'gateway': '1',
            'service': 'sinawap',
            'entry': 'sinawap',
            'useticket': '1',
            'returntype': 'META',
            'sudaref': '',
            '_client_version': '0.6.26',
        }
        murl = 'https://login.sina.com.cn/sso/login.php'
        mhtml = self.Session.get(murl, params=mParams)

        mpa = r'replace\((.*?)\);'
        mres = re.findall(mpa, mhtml.text)[0]  # 从新浪通行证中找到跳转链接

        mlogin = self.Session.get(eval(mres))

        m_weibo_com = 'https://m.weibo.cn'
        m_weibo_com_page = self.Session.get(m_weibo_com)

        login_start = m_weibo_com_page.text.index('login:')
        uid_start = m_weibo_com_page.text.index('uid:')

        print('移动端登录状态')
        print(m_weibo_com_page.text[login_start:login_start + 13:])
        print(m_weibo_com_page.text[uid_start:uid_start + 17:])

        # 旧版
        weibo_cn = 'https://weibo.cn'
        weibo_cn_page = self.Session.get(weibo_cn)

        return self.Session.cookies


def save(name, data):
    path = name + '.json'
    with open(path, 'w+') as f:
        json.dump(data, f)
        print(path, '保存成功')


def main():
    username = '18846426742'  # 用户名
    password = 'mdavid.cn'  # 密码
    login = WeiboLogin(username, password)
    cookies = login.get_cookie()

    cookie_name = 'cookie_' + username  # 保存 cookie 的文件名称
    data = cookies.get_dict()
    save(cookie_name, data)


main()
