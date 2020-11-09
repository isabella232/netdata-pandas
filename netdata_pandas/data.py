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


async def get_chart(api_call: str, data: list, col_sep: str ='|', numeric_only: bool = True, float_size: str = 'float64',
                    host_prefix: bool = False, host_sep: str = ':'):
    """Get data for an individual chart.

    ##### Parameters:
    - **api_call** `tuple` A tuple of (`url`,`chart`) for the url to pull data from and chart it represents.
    - **data** `list` A list for dataframes for each chart to be appended to.
    - **col_sep** `str` A character for separating chart and dimension in column names of dataframe.
    - **numeric_only** `bool` Set to true if you want to filter out any non numeric data.
    - **float_size** `str` float size to use if would like to save some memory, eg can use 'float32' or 'float16'.
    - **host_prefix** `bool` True to prefix each colname with the corresponding host.
    - **host_sep** `str` A character for separating host and chart and dimensions in column names of dataframe.

    """
    url, chart, host, user, pwd = api_call
    if user and pwd:
        user_pwd = (user, pwd)
        r = await asks.get(url, auth=BasicAuth(user_pwd))
    else:
        r = await asks.get(url)
    r_json = r.json()
    df = pd.DataFrame(r_json['data'], columns=['time_idx'] + r_json['labels'][1:])
    if host_prefix:
        df = df.set_index(['time_idx']).add_prefix(f'{host}{host_sep}{chart}{col_sep}')
    else:
        df['host'] = host
        df = df.set_index(['host','time_idx']).add_prefix(f'{chart}{col_sep}')
    if numeric_only:
        df = df._get_numeric_data().astype(float_size)
    data.append(df)



# Cell


async def get_charts(api_calls: list, col_sep: str ='|', timeout: int = 60, numeric_only: bool = True, float_size: str = 'float64',
                     host_prefix: bool = False, host_sep: str = ':') -> pd.DataFrame:
    """Create a nursey to make seperate async calls to get each chart.

    ##### Parameters:
    - **api_calls** `list` A list of tuple's of [(`url`,`chart`),...] of api calls that need to be made.
    - **col_sep** `str` A character for separating chart and dimension in column names of dataframe.
    - **timeout** `int` The number of seconds for trio to [move_on_after](https://trio.readthedocs.io/en/stable/reference-core.html#trio.move_on_after).
    - **numeric_only** `bool` Set to true if you want to filter out any non numeric data.
    - **float_size** `str` float size to use if would like to save some memory, eg can use 'float32' or 'float16'.
    - **host_prefix** `bool` True to prefix each colname with the corresponding host.
    - **host_sep** `str` A character for separating host and chart and dimensions in column names of dataframe.

    ##### Returns:
    - **df** `pd.DataFrame` A pandas dataframe with all chart data outer joined based on time index.

    """
    n_hosts = len(set([x[2] for x in api_calls]))
    data = []
    with trio.move_on_after(timeout):
        async with trio.open_nursery() as nursery:
            for api_call in api_calls:
                nursery.start_soon(get_chart, api_call, data, col_sep, numeric_only, float_size, host_prefix, host_sep)
    if n_hosts == 1 or host_prefix:
        df = pd.concat(data, join='outer', axis=1, sort=True)
    else:
        df = pd.concat(data, join='outer', axis=0, sort=True)
    return df



# Cell


def get_data(hosts: list = ['london.my-netdata.io'], charts: list = ['system.cpu'], after: int = -60,
             before: int = 0, points: int = 0, col_sep: str = '|', numeric_only: bool = True,
             ffill: bool = True, diff: bool = False, timeout: int = 60, nunique_thold = None,
             std_thold: float = None, index_as_datetime: bool = False, freq: str = 'infer',
             group: str = 'average', sort_cols: bool = True, user: str = None, pwd: str = None,
             protocol: str = 'http', sort_rows: bool = True, float_size: str = 'float64',
             host_charts_dict: dict = None, host_prefix: bool = False, host_sep: str = ':') -> pd.DataFrame:
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
    - **group** `str` The grouping function to use in the netdata api call.
    - **sort_cols** `bool` True to sort columns by name.
    - **user** `str` A username to use if netdata is password protected.
    - **pwd** `str` A password to use if netdata is password protected.
    - **protocol** `str` 'http' or 'https'.
    - **sort_rows** `bool` True to sort rows by index.
    - **float_size** `str` float size to use if would like to save some memory, eg can use 'float32' or 'float16'.
    - **host_charts_dict** `dict` dictionary of hosts to pull for where each value is list of relevant charts to pull from that host.
    - **host_prefix** `bool` True to prefix each colname with the corresponding host.
    - **host_sep** `str` A character for separating host and chart and dimensions in column names of dataframe.

    ##### Returns:
    - **df** `pd.DataFrame` A pandas dataframe with all chart data outer joined based on time index and any post processing done.

    """
    # if hosts is a string make it a list of one
    if isinstance(hosts, str):
        hosts = [hosts]

    # get list of host chart tuples we need to get data for
    if host_charts_dict:
        host_charts = [(k, v) for k in host_charts_dict for v in host_charts_dict[k]]
        hosts = list(set(host_charts_dict.keys()))
    elif charts == ['all']:
        host_charts = [(host, chart) for host in hosts for chart in get_chart_list(host)]
    else:
        host_charts = [(host, chart) for host in hosts for chart in charts]

    # define list of all api calls to be made
    api_calls = [
        (f'{protocol}://{host_chart[0]}/api/v1/data?chart={host_chart[1]}&after={after}&before={before}&points={points}&format=json&group={group}', host_chart[1], host_chart[0], user, pwd)
        for host_chart in host_charts
    ]
    # get the data
    df = trio.run(get_charts, api_calls, col_sep, timeout, numeric_only, float_size, host_prefix, host_sep)
    # post process the data
    if host_prefix:
        df = df.groupby(by=['time_idx']).max()
    else:
        df = df.groupby(by=['host','time_idx']).max()
    if len(hosts) == 1:
        df = df.reset_index(level=0, drop=True)
    if sort_rows:
        df = df.sort_index()
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


def get_allmetrics(host='london.my-netdata.io', charts: list = None, wide: bool = False, col_sep: str = '|', sort_cols: bool = True,
                   user: str = None, pwd: str = None, protocol: str = 'http', numeric_only: bool = True,
                   float_size: str = 'float64', host_charts_dict: dict = None, host_prefix: bool = False,
                   host_sep: str = ':') -> pd.DataFrame:
    """Get allmetrics into a df.

    ##### Parameters:
    - **host** `str` The host we want to get the alarm log from.
    - **charts** `list` A list of charts to pull data for.
    - **wide** `bool` True if you want to return the data in wide format as opposed to long.
    - **user** `str` A username to use if netdata is password protected.
    - **pwd** `str` A password to use if netdata is password protected.
    - **protocol** `str` 'http' or 'https'.
    - **numeric_only** `bool` Set to true if you want to filter out any non numeric data.
    - **float_size** `str` float size to use if would like to save some memory, eg can use 'float32' or 'float16'.

    ##### Returns:
    - **df** `pd.DataFrame` A df of the latest data from allmetrics.

    """

    if not host_charts_dict:
        host_charts_dict = {host: charts}

    data = []
    for host in host_charts_dict:
        charts = host_charts_dict[host]
        url = f'{protocol}://{host}/api/v1/allmetrics?format=json'
        if user and pwd:
            raw_data = requests.get(url, auth=HTTPBasicAuth(user, pwd)).json()
        else:
            raw_data = requests.get(url).json()
        if charts is None:
            charts = list(raw_data.keys())
        for k in raw_data:
            if k in charts:
                time = raw_data[k]['last_updated']
                dimensions = raw_data[k]['dimensions']
                for dimension in dimensions:
                    # [time, chart, name, value]
                    if host_prefix:
                        data.append(
                            [time, f"{host}{host_sep}{k}", f"{host}{host_sep}{k}{col_sep}{dimensions[dimension]['name']}", dimensions[dimension]['value']]
                        )
                    else:
                        data.append(
                            [time, k, "{}{}{}".format(k, col_sep, dimensions[dimension]['name']), dimensions[dimension]['value']]
                        )

    df = pd.DataFrame(data, columns=['time','chart','dimension','value'])
    if wide:
        df = df[['dimension', 'value']].groupby('dimension').mean().reset_index().pivot_table(columns=['dimension'])
        if sort_cols:
            df = df.reindex(sorted(df.columns), axis=1)
        if numeric_only:
            df = df._get_numeric_data().astype(float_size)
    return df

