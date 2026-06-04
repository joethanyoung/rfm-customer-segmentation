from yellowbrick.cluster import KElbowVisualizer
from sklearn import preprocessing
from datetime import datetime
from sklearn.preprocessing import MinMaxScaler
from sklearn.cluster import KMeans
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import datetime as dt
import os
os.environ['OMP_NUM_THREADS'] = '10'
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.float_format', lambda x: '%.5f' % x)
# =============================================================================
# data preprocessing
# =============================================================================
# conversion using Npad+ & read_csv
df = pd.read_csv(
    r'C:\Users\zhuoxun.yang001\Documents\fude\kmeans\军哥看这里\军哥看这里\2022.csv')
# check the information
df.head(5)
# check the shape of dataframe
df.shape
# using label indexing to check the values of certain 投保人客户号
df.loc[df['投保人客户号'] == 'C00000017866'].values
# check how many unique strings of products in dataframe
df["险种名称"].nunique()
# check how many unique customers
df['投保人客户号'].nunique()
# check how many unique numbers
df['投保单号'].nunique()
# check how many unique branches
df['二级机构名称'].nunique()
# check unique insurance invoice
df['保单号'].nunique()
# quantify the monetary value
df['money'] = df['综合标保']
# group monetary value by 投保单号
df.groupby("投保单号").agg({"money": "sum"}).head()
# group monetary value by 险种名称 and sort index in price following descending order
df.groupby("险种名称").agg({"保单保费": "max"}).sort_values(
    "保单保费", ascending=False).head()
# check the null values
df.isnull().sum()
# subset the columns to create new dataset
df1 = df[['机构代码', '二级机构名称', '保单号', '投保单号', '险种名称', '承保日期',
          '投保人姓名', '被保人姓名', '投保人客户号', '银行账号', 'money']]
# check the null value and sum up
df1.isnull().sum()
# drop the null value, name of subset listed below
df2 = df1.dropna(subset=['承保日期', '银行账号', 'money'])
# make sure the null value has been droped
df2.isnull().sum()
# check the dimension of dataframe 2
df2.shape
# check the dtype & counts of dataset
df2.info()
# =============================================================================
# calculate rfm score
# =============================================================================
# parsed the data by coerce transformation, in order to be processed
df2['date_parsed'] = pd.to_datetime(df2['承保日期'],
                                    infer_datetime_format=True,
                                    errors='coerce')
# set up Recency Metric
today_date = dt.datetime(2022, 9, 30, 23, 59, 59)
df2['hist'] = today_date - df2['date_parsed']
# then convert subset categories to timedelta64
df2['hist'].astype('timedelta64[D]')
# then applying timedelta of numpy to convert to days
df2['hist'] = df2['hist'] / np.timedelta64(1, 'D')
recency_df = df2.groupby('投保人客户号').agg({'hist': lambda x: round(x.min())})
recency_df.rename(columns={"hist": "Recency"}, inplace=True)
#  list recency
recency_df.head(5)
# add recency column with 1 to remove 0 or negative
recency_df['Recency'] = (recency_df['Recency'] + 1)
# check the null values in recency
recency_df.isnull().sum()
# Frequency Metric
temp_df = df.groupby(["投保人客户号", "投保单号"]).agg({"投保单号": "count"})
freq_df = temp_df.groupby("投保人客户号").agg({"投保单号": "count"})
freq_df.rename(columns={"投保单号": "Frequency"}, inplace=True)
# listed the frequency
freq_df.head(5)
# check the null value and sum up
freq_df.isnull().sum()
# Monetary Metric
monetary_df = df.groupby("投保人客户号").agg({"money": "sum"})
monetary_df.rename(columns={"money": "Monetary"}, inplace=True)
monetary_df.head(5)
# check the null value and sum up
monetary_df.isnull().sum()
# concat three columns and drop null value in column recency
rfm = pd.concat([recency_df, freq_df, monetary_df], axis=1)
rfm = rfm.dropna(subset=['Recency'])
df3 = rfm
rfm.head(5)
# check the dtype and counts
rfm.info()
# make sure no null value
rfm.isnull().sum()
# quantile the recency, frequency, monetary, and combine them and set their data type to string
df3["RecencyScore"] = pd.qcut(rfm['Recency'], 5, labels=[5, 4, 3, 2, 1])
df3["FrequencyScore"] = pd.qcut(rfm['Frequency'].rank(
    method="first"), 5, labels=[1, 2, 3, 4, 5])
df3["MonetaryScore"] = pd.qcut(rfm['Monetary'], 5, labels=[1, 2, 3, 4, 5])
df3["RFM_SCORE"] = rfm['RecencyScore'].astype(
    str) + rfm['FrequencyScore'].astype(str) + rfm['MonetaryScore'].astype(str)
# check the head
df3.head(5)
# build up a value named seg_map, map the values to dataframe
seg_map = {
    r'[1-3][1-3][1-3]': '一般挽留客户',
    r'[3-5][1-3][1-3]': '一般发展客户',
    r'[1-3][3-5][1-3]': '一般保持客户',
    r'[3-5][3-5][1-3]': '一般价值客户',
    r'[1-3][1-3][3-5]': '重要挽留客户',
    r'[3-5][1-3][3-5]': '重要发展客户',
    r'[1-3][3-5][3-5]': '重要保持客户',
    r'[3-5][3-5][3-5]': '重要价值客户'
}

df3['用户分类'] = df3['RecencyScore'].astype(
    str) + df3['FrequencyScore'].astype(str) + df3['MonetaryScore'].astype(str)
df3['用户分类'] = df3['用户分类'].replace(seg_map, regex=True)
df3.head(5)
# subset the columns
df4 = df3.loc[:, "Recency":"Monetary"]
print(df4.head(5))
# group by 投保人客户号
df3.groupby("投保人客户号").agg({"用户分类": "sum"}).head()
# check the head of dataframe3
df3.head(5)
# =============================================================================
# apply unsupervised algorithm ---kmeans clustering
# =============================================================================
# k means clustering
# apply sklearn preprocessing to encode label, transform to numerical value
rfm_encoded = rfm
le = preprocessing.LabelEncoder()
rfm_encoded['用户分类'] = le.fit_transform(rfm_encoded['用户分类'])
print(rfm_encoded.head(5))
# scale
sc = MinMaxScaler((0, 1))
df5 = sc.fit_transform(rfm_encoded)
# set kemeans clustering model with k = 10(emperical view)
kmeans = KMeans(n_clusters=10)
k_fit = kmeans.fit(df5)
# fit clusters
k_fit.n_clusters
# use k = 10 the clusters centers, identify the centers
k_fit.cluster_centers_
# fit k with labels
k_fit.labels_
# measure wellness of cluster
k_fit.inertia_
# write function and fit the clusters
kmeans = KMeans(n_clusters=2)
k_fit = kmeans.fit(df5)
ssd = []

K = range(2, 30)

for k in K:
    kmeans = KMeans(n_clusters=k).fit(df5)
    ssd.append(kmeans.inertia_)

plt.plot(K, ssd, "bx-")
plt.xlabel("Sums of residuals Versus Different k Values")
plt.title("Elbow method")
# import Elbow visualizer to visulize and to find the optimal number of k
kmeans = KMeans()
visu = KElbowVisualizer(kmeans, k=(2, 30))
visu.fit(df5)
visu.show()
# =============================================================================
# fit kmeans
# =============================================================================
# Use optimal k = 9 to fit model
kmeans = KMeans(n_clusters=9).fit(df5)
kmeans_num = kmeans.labels_
kmeans_df = pd.DataFrame({"投保人客户号": rfm.index, "聚类组": kmeans_num})
# tranform index to index + 1 for visulize and readness
rfm["cluster_no"] = kmeans_num
rfm["cluster_no"] = rfm["cluster_no"] + 1
rfm.groupby("cluster_no").agg({"cluster_no": "count"})
# check the head
rfm.head(5)
# rename column and update immediately
rfm.rename(columns={'用户分类': 'Client_seg'}, inplace=True)
rfm.head(5)
# =============================================================================
# inverse code and rearrange categories
# =============================================================================
# transform the encoder for machine learning binary value to categorical strings
to_encode = ["Client_seg"]
for col in to_encode:
    rfm[col] = le.inverse_transform(rfm[col])
# filtered out the clients with required columns names and subset the categories
options = ["重要价值客户", "重要保持客户", "重要发展客户", "重要挽留客户", "一般价值客户", "一般保持客户",
           "一般发展客户", "一般挽留客户"]
rfm_filtered = rfm[rfm["Client_seg"].isin(options)]
# check the head after filtered
rfm_filtered.head(5)
# check the dimension of rfm
rfm_filtered.shape
# convert dataframe of specific columns to numpy array
df_sep = df2.drop_duplicates(['投保人客户号', '二级机构名称'])
df_sep.head(5)
# check the dim of df2
df_sep.shape
# match rfm_filtered table with original table to embellish the table
rfm_full = rfm_filtered.merge(
    df_sep[['二级机构名称', '投保人客户号']], how='left', on='投保人客户号')
# mcheck the shape of the dataframe
rfm_full.shape
#
rfm_full.head(5)
output = 'C://Users//zhuoxun.yang001//Documents//fude//kmeans//军哥看这里//军哥看这里//2022gxcbqd_rfm_readyto_profile.xlsx'
rfm_full.to_excel(output)
