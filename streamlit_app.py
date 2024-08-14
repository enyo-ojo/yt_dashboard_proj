
''' 
Created on Wednesday August 2024

@author : Enyojo Alabi
'''

#import libs
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

#define funtions: 
def style_negative(v, props=''):
    """ Style negative values in dataframe"""
    try: 
        return props if v < 0 else None
    except:
        pass
    
def style_positive(v, props=''):
    """Style positive values in dataframe"""
    try: 
        return props if v > 0 else None
    except:
        pass  

def audience_sample(country):
    ''' Show Top Countries '''
    if country == 'US':
        return 'USA'
    elif country == 'IN':
        return 'India'
    else:
        return 'Other'

#load data:
def loadData():
    df_comments = pd.read_csv('/workspaces/enyo-ojo/stenv/csv-files/All_Comments_Final.csv')
    df_vp_time = pd.read_csv('/workspaces/enyo-ojo/stenv/csv-files/Video_Performance_Over_Time.csv')
    df_agg = pd.read_csv('/workspaces/enyo-ojo/stenv/csv-files/Aggregated_Metrics_By_Video.csv').iloc[1:,:]
    df_agg_sub = pd.read_csv('/workspaces/enyo-ojo/stenv/csv-files/Aggregated_Metrics_By_Country_And_Subscriber_Status.csv')

    #renaming the agg columns
    df_agg.columns = ['Video','Video title','Video publish time','Comments added','Shares','Dislikes','Likes',
                        'Subscribers lost','Subscribers gained','RPM(USD)','CPM(USD)','Average % viewed','Average view duration',
                        'Views','Watch time (hours)','Subscribers','Your estimated revenue (USD)','Impressions','Impressions ctr(%)']
    #coverting time from string to datetime to allow time based operations and calculations
    df_vp_time['Date'] = pd.to_datetime(df_vp_time['Date'], errors='coerce')
    df_agg['Video publish time'] = pd.to_datetime(df_agg['Video publish time'], format= '%b %d, %Y' )
    #converting using a specified data time format that includes seconds because t is a continous variabble therefore making it more useful
    df_agg['Average view duration'] = df_agg['Average view duration'].apply(lambda x: datetime.strptime(x, '%H:%M:%S'))

    #creating useful colum metrics for analysis in agg
    df_agg['Avg_duration_sec'] = df_agg['Average view duration'].apply(lambda x: x.second + x.minute*60 + x.hour*3600)
    df_agg['Engagement ratio'] = (df_agg['Comments added'] + df_agg['Shares'] + df_agg['Dislikes'] + df_agg['Likes']) / df_agg['Views']
    df_agg['Views/Subs gained'] = df_agg['Views'] / df_agg['Subscribers gained']

    #sort agg by vide publish time
    df_agg.sort_values('Video publish time', ascending =False, inplace =True)
    return df_agg, df_agg_sub, df_comments, df_vp_time
df_agg, df_agg_sub, df_comments, df_vp_time = loadData()

#Data Engineering:
#create a copy of df_agg to prevent errors
df_agg_diff =  df_agg.copy()
#using videos from only the past 1year
metricDate_12months = df_agg_diff['Video publish time'].max() - pd.DateOffset(months=12)
#filter the data to get median of all the columns in last 1 year, first get only thenumeric columns
numeric_columns = df_agg_diff.select_dtypes(include='number').columns
median_agg = df_agg_diff[df_agg_diff['Video publish time'] >= metricDate_12months][numeric_columns].median()


# Normalize the numeric columns using the median values
#this gives us the %diff useful for analysis and useful for visualization
numeric_cols = np.array((df_agg_diff.dtypes == 'float64') | (df_agg_diff.dtypes == 'int64'))
df_agg_diff.iloc[:,numeric_cols] = (df_agg_diff.iloc[:,numeric_cols] - median_agg).div(median_agg)

#merge the publish data with the daily data to get the video length term my subracticting the video pubished date and current date for time series graph
df_time_diff = pd.merge(df_vp_time, df_agg.loc[:,['Video', 'Video publish time']], left_on='External Video ID', right_on='Video')
df_time_diff['days_published'] = (df_time_diff['Date'] - df_time_diff['Video publish time']).dt.days

#get the time diff data for only last 1yr
date_12months = df_agg['Video publish time'].max() - pd.DateOffset(months=12)
df_time_diff_yr = df_time_diff[df_time_diff['Video publish time'] >= date_12months]

#create a pivot table(alt : group by) to show views on average in the first 30 days along with other agg func(s)
views_days = pd.pivot_table(df_time_diff_yr,index= 'days_published',values ='Views', aggfunc = [np.mean,np.median,lambda x: np.percentile(x, 80),lambda x: np.percentile(x, 20)]).reset_index()
views_days.columns = ['days_published','mean_views','median_views','80pct_views','20pct_views']
views_days = views_days[views_days['days_published'].between(0,30)]
views_cumulative = views_days.loc[:,['days_published','median_views','80pct_views','20pct_views']]   #views sum
views_cumulative.loc[:,['median_views','80pct_views','20pct_views']] = views_cumulative.loc[:,['median_views','80pct_views','20pct_views']].cumsum()



###############################################################################
#Start building Streamlit App
###############################################################################

#Build Dashboard:
#1.sidebar to show the different features
sidebar = st.sidebar.selectbox('Aggregate or Individual Video', ('Aggregate Metrics', 'Individual Video Analysis'))

if sidebar == 'Aggregate Metrics':
    st.write('Agg')
    #create a new df with the desired columns
    df_agg_metrics = df_agg[['Video publish time','Views','Likes','Subscribers','Shares','Comments added','RPM(USD)','Average % viewed',
                             'Avg_duration_sec', 'Engagement ratio','Views/Subs gained']]
    #get the median for 6 and 12 months
    metric_date_6mo = df_agg_metrics['Video publish time'].max() - pd.DateOffset(months=6)
    metric_date_12mo = df_agg_metrics['Video publish time'].max() - pd.DateOffset(months=12)
    metrics_median6mo = df_agg_metrics[df_agg_metrics['Video publish time'] >= metric_date_6mo].median()
    metrics_median12mo = df_agg_metrics[df_agg_metrics['Video publish time'] >= metric_date_12mo].median()

    #creating 5 colums so we can have the metrics organised in a row
    col1, col2, col3, col4, col5 = st.columns(5)
    columns = [col1, col2, col3, col4, col5]

    #getting a delta value to show %inc or decrease for each metric
    count = 0
    for i in metrics_median6mo.index:
        # Ensure the metric is numeric
        if pd.api.types.is_numeric_dtype(metrics_median6mo[i]) and pd.api.types.is_numeric_dtype(metrics_median12mo[i]):
            #adding Streamlit elements to the column at position count.
            with columns[count]:
                delta = (metrics_median6mo[i] - metrics_median12mo[i]) / metrics_median12mo[i]
                st.metric(label=i, value = round(metrics_median6mo[i],1), delta= "{:.2%}".format(delta))
                count +=1
                #reseting the count cos we have only 5 cols therefore a new row is needed
                if count >=5:
                    count = 0

    #creating the table, seleting the needed cols
    #convert video-pt to date format
    df_agg_diff['Publish date'] = df_agg_diff['Video publish time'].apply(lambda x:x.date())
    df_agg_diff_final = df_agg_diff.loc[:,['Video title', 'Publish date','Views','Likes','Subscribers','Shares','Comments added','RPM(USD)','Average % viewed',
                                'Avg_duration_sec', 'Engagement ratio','Views/Subs gained']] 

    #converting numeric cols to %
    df_agg_numeric_list = df_agg_diff_final.select_dtypes(include='number').columns.tolist()    #getting a list of all the num cols in df
    df_to_pct = {}   #a dict to store the new % format
    for i in df_agg_numeric_list:
        df_to_pct[i] = '{:.1%}'.format

    #display and style tableb
    st.dataframe(df_agg_diff_final.style.hide().applymap(style_negative, props = 'color:red;').applymap(style_positive, props = 'color:green;').format(df_to_pct))

if sidebar == 'Individual Video Analysis':
    videos = tuple(df_agg['Video title'])
    video_selection = st.selectbox('Pick a Video:', (videos))                   #note: a tuple is an uniterable list

    #create a filter for selected video
    filtered_agg = df_agg[df_agg['Video title'] == video_selection]
    filtered_agg_sub = df_agg_sub[df_agg_sub['Video Title'] == video_selection]    #using the second df to get the sub countrys data
    
    #grouping by country; us, india and others
    filtered_agg_sub['Country'] = filtered_agg_sub['Country Code'].apply(audience_sample)
    filtered_agg_sub.sort_values('Is Subscribed', inplace=True)

    #first graph using plotly showing sub? by country
    fig = px.bar(filtered_agg_sub, x='Views', y='Is Subscribed', color='Country', orientation='h')
    st.plotly_chart(fig)

    #second time series graph that shows the selcted video views comparison by percentiles
    
    agg_time_filtered = df_time_diff[df_time_diff['Video Title'] == video_selection]
    first_30 = agg_time_filtered[agg_time_filtered['days_published'].between(0,30)]
    first_30 = first_30.sort_values('days_published')
    
    
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=views_cumulative['days_published'], y=views_cumulative['20pct_views'],
                    mode='lines',
                    name='20th percentile', line=dict(color='purple', dash ='dash')))
    fig2.add_trace(go.Scatter(x=views_cumulative['days_published'], y=views_cumulative['median_views'],
                        mode='lines',
                        name='50th percentile', line=dict(color='black', dash ='dash')))
    fig2.add_trace(go.Scatter(x=views_cumulative['days_published'], y=views_cumulative['80pct_views'],
                        mode='lines', 
                        name='80th percentile', line=dict(color='royalblue', dash ='dash')))
    fig2.add_trace(go.Scatter(x=first_30['days_published'], y=first_30['Views'].cumsum(),
                        mode='lines', 
                        name='Current Video' ,line=dict(color='firebrick',width=8)))
        
    fig2.update_layout(title='View comparison first 30 days',
                   xaxis_title='Days Since Published',
                   yaxis_title='Cumulative views')
    
    st.plotly_chart(fig2)

