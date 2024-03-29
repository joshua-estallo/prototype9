from django.shortcuts import render, redirect
from django.db.models import Q
from django.http import HttpResponse
from .models import Dataset
from .forms import DatasetForm  
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import pandas as pd
import csv
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer


# ALGORITHM
def give_recommendations(id):
  datasets = Dataset.objects.filter(archived=0)

  # Convert the Django QuerySet to a list of dictionaries
  data_dict = list(datasets.values())
  
  # Create a Pandas DataFrame from the list of dictionaries
  df = pd.DataFrame(data_dict)
  
  # Filling NaNs with empty string
  df["overview"] = df["overview"].fillna('')
  
  # Create a TFIDFVectorizer Object
  tfv = TfidfVectorizer(min_df=1, max_features=None, strip_accents="unicode", analyzer="word", token_pattern=r"\w{1,}", ngram_range=(1, 3), stop_words="english")
  
  # Fit the TfidfVectorizer on the "overview" text
  tfv_matrix = tfv.fit_transform(df["overview"])
  
  # Calculate the cosine similarity between all dataset
  cos_sim = cosine_similarity(tfv_matrix, tfv_matrix)

  id_to_index = {str(id_): index for index, id_ in enumerate(df["id"])}
  idx = id_to_index[str(id)]
  
  cos_sim_scores = list(enumerate(cos_sim[idx]))
  
  # Filter out datasets with a cosine similarity score of less than .00
  cos_sim_scores = [cos_sim_score for cos_sim_score in cos_sim_scores if cos_sim_score[1] > 0.00]
  cos_sim_scores = sorted(cos_sim_scores, key=lambda x: x[1], reverse=True)
  cos_sim_scores = cos_sim_scores[1:6]
  
  # Dataset indices
  dataset_indices = [cos_sim_score[0] for cos_sim_score in cos_sim_scores]
  similar_ids = [df.iloc[index]["id"] for index in dataset_indices]
  
  return similar_ids, cos_sim_scores
  

def dataset(request, pk):
  current_dataset = Dataset.objects.get(id=pk)
  name = current_dataset.project_head
  lastname = name.split(", ")[0]
  pks, scores = give_recommendations(current_dataset.id)
  similar_datasets = []
  # Primary Keys
  for pk in pks:
    similar_datasets.append(Dataset.objects.get(id=pk))
  return render(request, "base/dataset.html", {"dataset" : current_dataset, 
                                                "similar_datasets" : similar_datasets, 
                                                "scores" : scores, 
                                                "pks" : pks, 
                                                "year" : current_dataset.date_uploaded.year,
                                                "lastname" : lastname })


# HOME PAGE
def home(request):
  data_types = DatasetForm.base_fields['data_type'].choices
  q = request.GET.get('q', '') 
  type_filter = request.GET.get("type", "")
  datasets = Dataset.objects.filter(archived=0)
  if type_filter and not q:
    datasets = datasets.filter(
      Q(data_type__icontains=type_filter) 
    ).order_by("id")
  else:
    datasets = datasets.filter(
      Q(data_type__icontains=type_filter) &
      (Q(title__icontains=q) |
      Q(overview__icontains=q) )
    ).order_by("id")


  datasets_per_page = 10
  paginator = Paginator(datasets, datasets_per_page)

  # Get the current page number from the request's GET parameters
  page_number = request.GET.get('page')

  # Get the Page object for the current page
  page = paginator.get_page(page_number)
  return render(request, "base/home.html", {"page" : page, "q" : q, "datasets" : datasets, "data_types" : data_types})


# archived datasets
def archived_datasets(request):
  datasets = Dataset.objects.filter(archived=1)
  datasets_per_page = 10
  paginator = Paginator(datasets, datasets_per_page)

  # Get the current page number from the request's GET parameters
  page_number = request.GET.get('page')

  # Get the Page object for the current page
  page = paginator.get_page(page_number)
  return render(request, "base/archived_datasets.html", {"page" : page, "datasets" : datasets,})

# UPLOAD PAGE
def upload(request):
  if request.method == "POST":
    form = DatasetForm(request.POST, request.FILES)
    if form.is_valid():
      dataset = form.save()
      overview = f" {dataset.title}. {dataset.description} {dataset.tags}. {dataset.category}."
      dataset.overview = overview
      dataset.save()
      return redirect("home")
  else:
    form = DatasetForm()
  return render(request, "base/upload.html", {"form" : form})


def update(request, pk):
  dataset = Dataset.objects.get(id=pk)
  if request.method == "POST":
    form = DatasetForm(request.POST, request.FILES, instance=dataset)
    if form.is_valid():
      dataset = form.save()
      dataset.overview = f" {dataset.title}. {dataset.description} {dataset.tags}. {dataset.category}."
      dataset.save()
      return redirect("dataset", pk=dataset.id)
  else:
    initial_category = [category.strip("' ") for category in dataset.category.strip("[]").split(",")] if dataset.category else []
    print(initial_category)
    form = DatasetForm(instance=dataset, initial={"category" : initial_category})
  return render(request, "base/update.html", {"form" : form, "pk" : pk})


def archive(request, pk):
  dataset = Dataset.objects.get(id=pk)
  dataset.archived = 1
  dataset.save()
  return redirect("home")

def unarchive(request, pk):
  dataset = Dataset.objects.get(id=pk)
  dataset.archived = 0
  dataset.save()
  return redirect("archived_datasets")

  
def download(request, pk):
  file = Dataset.objects.get(id=pk)
  response = HttpResponse(file.file, content_type='application/force-download')
  response['Content-Disposition'] = f'attachment; filename="{file.file.name}"'
  return response
