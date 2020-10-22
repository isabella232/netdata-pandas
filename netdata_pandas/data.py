# AUTOGENERATED! DO NOT EDIT! File to edit: 00_data.ipynb (unless otherwise specified).

__all__ = ['get_chart_list', 'get_chart', 'get_charts', 'get_data', 'get_alarm_log', 'get_allmetrics']

# Cell
# export
import asks
from asks import BasicAuth
import trio
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth
from .wrangle import drop_low_uniqueness_cols, drop_low_std_cols

# Cell


def get_chart_list(host: str = '127.0.0.1:19999', starts_with: str = None) -> list:
    """Get list of all available charts on a `host`.

    ##### Parameters:
    - **host** `str` The host we want to get a list of available charts from.
    - **starts_with** `str` A string to filter the list of charts returns to just those that start with `starts_with`.

    ##### Returns:
    - **chart_list** `list` A list of availalbe charts.

    """

    url = f"http://{host}/api/v1/charts"
    r = requests.get(url)
    charts = r.json().get('charts')
    chart_list = [chart for chart in charts]
    if starts_with:
        chart_list = [chart for chart in chart_list if chart.startswith(starts_with)]
    return chart_list

# Cell


async def get_chart(api_call: str, data: list, col_sep: str ='|'):
    """Get data for an individual chart.

    ##### Parameters:
    - **api_call** `tuple` A tuple of (`url`,`chart`) for the url to pull data from and chart it represents.
    - **data** `list` A list for dataframes for each chart to be appended to.
    - **col_sep** `str` A character for separating chart and dimension in column names of dataframe.

    """

    url, chart, host, user, pwd = api_call
    if user and pwd:
        user_pwd = (user, pwd)
        r = await asks.get(url, auth=BasicAuth(user_pwd))
    else:
        r = await asks.get(url)
    r_json = r.json()
    df = pd.DataFrame(r_json['data'], columns=['time_idx'] + r_json['labels'][1:])
    df['host'] = host
    df = df.set_index(['host','time_idx']).add_prefix(f'{chart}{col_sep}')
    data.append(df)



# Cell


async def get_charts(api_calls: list, col_sep: str ='|', timeout: int = 60) -> pd.DataFrame:
    """Create a nursey to make seperate async calls to get each chart.

    ##### Parameters:
    - **api_calls** `list` A list of tuple's of [(`url`,`chart`),...] of api calls that need to be made.
    - **col_sep** `str` A character for separating chart and dimension in column names of dataframe.
    - **timeout** `int` The number of seconds for trio to [move_on_after](https://trio.readthedocs.io/en/stable/reference-core.html#trio.move_on_after).

    ##### Returns:
    - **df** `pd.DataFrame` A pandas dataframe with all chart data outer joined based on time index.

    """

    data = []
    with trio.move_on_after(timeout):
        async with trio.open_nursery() as nursery:
            for api_call in api_calls:
                nursery.start_soon(get_chart, api_call, data, col_sep)
    #df = pd.concat(data, join='outer', axis=1, sort=True)
    df = pd.concat(data, join='outer', axis=0, sort=True)
    return df



# Cell


def get_data(hosts: list = ['london.my-netdata.io'], charts: list = ['system.cpu'], after: int = -60,
             before: int = 0, points: int = 0, col_sep: str = '|', numeric_only: bool = False,
             ffill: bool = True, diff: bool = False, timeout: int = 60, nunique_thold = None,
             std_thold: float = None, index_as_datetime: bool = False, freq: str = 'infer',
             group: str = 'average', sort_cols: bool = True, user: str = None, pwd: str = None,
             protocol: str = 'http', sort_rows: bool = True) -> pd.DataFrame:
    """Define api calls to make and any post processing to be done.

    ##### Parameters:
    - **hosts** `list` A list of hosts to pull data from.
    - **charts** `list` A list of charts to pull data for.
    - **after** `int` The timestamp or relative integer from which to pull data after.
    - **before** `int` The timestamp or relative integer from which to pull data before.
    - **points** `int` The `points` parameter to pass to the api call if need to aggregate data in some way.
    - **col_sep** `str` A character for separating chart and dimension in column names of dataframe.
    - **numeric_only** `bool` Set to true if you want to filter out any non numeric data.
    - **ffill** `bool` Set to true if you want to forward fill any null or missing values.
    - **diff** `bool` Set to true if you want to get the difference of metrics as opposed to their raw value.
    - **timeout** `int` The number of seconds for trio to [move_on_after](https://trio.readthedocs.io/en/stable/reference-core.html#trio.move_on_after).
    - **nunique_thold** [`float`,`int`] If defined calls function to filter cols with low number of unique values.
    - **std_thold** `float` If defined calls function to filter cols with low standard deviation.
    - **index_as_datetime** `bool` If true, set the index to be a pandas datetime.
    - **freq** `str` Freq to be passed to pandas datetime index.
    - **group** `str` The grouping function to use.
    - **sort_cols** `bool` True to sort columns by name.
    - **user** `str` A username to use if netdata is password protected.
    - **pwd** `str` A password to use if netdata is password protected.
    - **protocol** `str` 'http' or 'https'.
    - **sort_rows** `bool` True to sort rows by index.

    ##### Returns:
    - **df** `pd.DataFrame` A pandas dataframe with all chart data outer joined based on time index and any post processing done.

    """

    # if hosts is a string make it a list of one
    if isinstance(hosts, str):
        hosts = [hosts]

    # if charts is a string make it a list of one
    if isinstance(charts, str):
        # if specified get all charts
        if charts == 'all':
            charts = get_chart_list(hosts[0])
        else:
            charts = [charts]

    # define list of all api calls to be made
    api_calls = [
        (f'{protocol}://{host}/api/v1/data?chart={chart}&after={after}&before={before}&points={points}&format=json&group={group}', chart, host, user, pwd)
        for host in hosts for chart in charts
    ]
    # get the data
    df = trio.run(get_charts, api_calls, col_sep, timeout)
    # post process the data
    df = df.groupby(by=['host','time_idx']).max()
    if len(hosts) == 1:
        df = df.reset_index(level=0, drop=True)
    if sort_rows:
        df = df.sort_index()
    if numeric_only:
        df = df._get_numeric_data()
    if ffill:
        df = df.ffill()
    if diff:
        df = df.diff().dropna(how='all')
    if nunique_thold:
        df = drop_low_uniqueness_cols(df, nunique_thold)
    if std_thold:
        df = drop_low_std_cols(df, std_thold)
    if index_as_datetime:
        df = df.set_index(pd.DatetimeIndex(pd.to_datetime(df.index, unit='s'), freq=freq))
    if sort_cols:
        df = df.reindex(sorted(df.columns), axis=1)
    return df



# Cell


def get_alarm_log(host: str = '127.0.0.1:19999', datetimes: bool = True, user: str = None,
                  pwd: str = None, protocol: str = 'http') -> pd.DataFrame:
    """Get alarm log from `host`.

    ##### Parameters:
    - **host** `str` The host we want to get the alarm log from.
    - **user** `str` A username to use if netdata is password protected.
    - **pwd** `str` A password to use if netdata is password protected.
    - **protocol** `str` 'http' or 'https'.

    ##### Returns:
    - **df** `pd.DataFrame` A df of the alarm_log.

    """

    url = f"{protocol}://{host}/api/v1/alarm_log"
    if user and pwd:
        r = requests.get(url, auth=HTTPBasicAuth(user, pwd))
    else:
        r = requests.get(url)
    alarm_log = r.json()
    df = pd.DataFrame(alarm_log)
    if datetimes:
        for col in ['when', 'delay_up_to_timestamp']:
            df[col] = pd.to_datetime(df[col], unit='s')
    return df



# Cell


def get_allmetrics(host, charts: list = None, wide: bool = False, col_sep: str = '|', sort_cols: bool = True,
                   user: str = None, pwd: str = None, protocol: str = 'http') -> pd.DataFrame:
    """Get allmetrics into a df.

    ##### Parameters:
    - **host** `str` The host we want to get the alarm log from.
    - **charts** `list` A list of charts to pull data for.
    - **wide** `bool` True if you want to return the data in wide format as opposed to long.
    - **user** `str` A username to use if netdata is password protected.
    - **pwd** `str` A password to use if netdata is password protected.
    - **protocol** `str` 'http' or 'https'.

    ##### Returns:
    - **df** `pd.DataFrame` A df of the latest data from allmetrics.

    """

    url = f'{protocol}://{host}/api/v1/allmetrics?format=json'
    if user and pwd:
        raw_data = requests.get(url, auth=HTTPBasicAuth(user, pwd)).json()
    else:
        raw_data = requests.get(url).json()
    if charts is None:
        charts = list(raw_data.keys())
    data = []
    for k in raw_data:
        if k in charts:
            time = raw_data[k]['last_updated']
            dimensions = raw_data[k]['dimensions']
            for dimension in dimensions:
                # [time, chart, name, value]
                data.append(
                    [time, k, "{}{}{}".format(k, col_sep, dimensions[dimension]['name']), dimensions[dimension]['value']]
                )
    df = pd.DataFrame(data, columns=['time','chart','dimension','value'])
    if wide:
        df = df[['dimension', 'value']].groupby('dimension').mean().reset_index().pivot_table(columns=['dimension'])
        if sort_cols:
            df = df.reindex(sorted(df.columns), axis=1)
    return df

