#' Read data for ANTS 2020 paper and create plots for the Experiments
#' section of the paper

source("myplothelpers.R")
library(stringr)

# General Settings ------------------------------------------------------
actual.frequency <- 32 ## Actual frequency of white tiles
base.dir <- "../"
multiplier <- 10000000
tau <- 0.02
data.dir <- file.path(base.dir, "data")
plot.dir <- file.path(base.dir, "plots")

# Function Declarations -------------------------------------------------

#' Read event.csv file from a randomly selected robot
sample_event_log <- function(run.path) {
    robots <- list.dirs(run.path, recursive = FALSE)
    sampled.robot <- sample(robots, 1)
    event.file <- file.path(sampled.robot, "event.log")    
    event.df <- read.csv(event.file, sep=' ')
}

#' Read event.csv file from a randomly selected robot
all_event_logs <- function(run.path) {
    robots <- list.dirs(run.path, recursive = FALSE)
    all.event.logs <- file.path(robots, "event.log")

    for (robot in all.event.logs) {
        event.file <- file.path(robot, "event.log")
        event.df <- read.csv(event.file, sep=' ')
    }
}


#' Get the mean where a consensus has been reached from an event.csv
#' file
get_final_mean <- function(event.df, consensus.reached.at) {
    means <- event.df$MEAN
    final.mean <- means[consensus.reached.at] / 100000

    return(final.mean)
}

#' TODO: One function for both values
get_final_time <- function(event.df, consensus.reached.at) {
    times <- event.df$TIME
    final.time <- times[consensus.reached.at]

    return(final.time)
}

find.consensus <- function(sc.df, num.robots, tau) {

    # Find position in dataframe where the consensus is reached for
    # the first time
    pos <- min(which(sc.df$C == "True"))

    # Return position and time of positions
    return(c(pos, sc.df$TIME[pos]))
}


postprocess <- function(run.path, tau) {

    # Find number of robots again (TODO: use as argument)
    num.robots <- strtoi(str_match(run.path,
                            "(\\d+)robots-(\\d)byz-(\\d+)$")[2])


    robots <- list.dirs(run.path, recursive = FALSE)
    all.event.logs <- file.path(robots, "sc.csv")

    all.consensus.reached.at.time <- c()
    all.consensus.reached.at.pos <- c()

    print(all.event.logs)
    for (event.file in all.event.logs) {
        event.df <- read.csv(event.file, sep=' ')

        # Get consensus time and position in dataframe
        cons.time.and.position <-  find.consensus(event.df,
                                                  num.robots,
                                                  tau)

        consensus.reached.at.pos <- cons.time.and.position[1]
        consensus.reached.at.time <- cons.time.and.position[2]


        
        all.consensus.reached.at.time <- c(all.consensus.reached.at.time,
                                           consensus.reached.at.time)

        all.consensus.reached.at.pos <- c(all.consensus.reached.at.pos,
                                          consensus.reached.at.pos)
        
    }

    error.file <- "none"
    
    # Which event.df contained the maximum time?
    max.time.pos <- which.max(all.consensus.reached.at.time)
    print(all.consensus.reached.at.time)
    print(max.time.pos)

    if (length(max.time.pos) == 0) {
        consensus.reached.at <- NA
        final.mean <- NA
        final.time <- NA
        error.file <- "all.failed"

    ##  Check if all robots received a consensus signal

     } else if (any(is.na(all.consensus.reached.at.time))) {
         consensus.reached.at <- NA
         final.mean <- NA
         final.time <- NA
         error.file <- all.event.logs[min(which(is.na(all.consensus.reached.at.time)))]

    } else {
        # At which position is the consenus agreement in that df?
        consensus.reached.at <-  all.consensus.reached.at.pos[max.time.pos]

        event.df <- read.csv(all.event.logs[max.time.pos], sep=' ')


        # We take the mean of the robot that reached consensus last;
        # it's better to sample a random robot
        final.mean <- get_final_mean(event.df, consensus.reached.at)

        final.time <- get_final_time(event.df, consensus.reached.at)

    }

    return(c(consensus.reached.at,
             final.mean,
             final.time,
             error.file))
    }


#' Create a dataframe of all runs and calculate the absolute error
create.df <- function(experiment.path, tau) {
    experiments <- list.dirs(experiment.path, recursive=FALSE,
                             full.names = FALSE)
    experiments.with.path <- list.dirs(experiment.path,
                                       recursive=FALSE)
    
    # Extract information about that run using a regex:
    # - Number of robots
    # - Number of Byzantines
    # - Repetition number
    all.experiments.matrix <- str_match(experiments,
                                        "^(\\d+)robots-(\\d)byz-(\\d+)$")

    # Create a data frame with all information from all runs
    df <- as.data.frame(all.experiments.matrix)
    colnames(df) <- c("path", "num.robots", "byz", "run")
    df$num.robots <- as.numeric(as.character(df$num.robots))
    df$byz <- as.numeric(as.character(df$byz))

    df$full.path <- experiments.with.path
    df <- na.omit(df) # Remove invalid runs

    # Needed are:
    # - position of consensus
    # - the final mean
    # - consensus time

    postprocessed <- lapply(df$full.path, postprocess, tau)
    postprocessed.df <- data.frame(matrix(unlist(postprocessed),
                                          nrow=length(postprocessed),
                                          byrow=T))

    colnames(postprocessed.df) <- c("consensus.reached.at",
                                    "final.mean",
                                    "final.time",
                                    "error.file")

    df <- cbind(df, postprocessed.df)

    df$consensus.reached.at <- as.numeric(as.character(df$consensus.reached.at))
    df$final.mean <- as.numeric(as.character(df$final.mean))
    df$final.time <- as.numeric(as.character(df$final.time))
    df$error.file <- as.character(df$error.file)
    
    df$selected.absError <- abs(df$final.mean - actual.frequency)

    return(df)
    }


# Experiment 1  ------------------------------------------------------------

experiment.1.path <- file.path(data.dir, "experiment_1")
df.1 <- create.df(experiment.1.path, tau)

# Plot selected absolute error
plot.x.by.y(df.1,
            x="byz",
            y="selected.absError",
            xlab=expression("Number of Byzantine robots"),
            ylab=expression("Absolute error (in %)"),
            out.name=sprintf("exp1_error.pdf"),
            report.dir=plot.dir,
            custom.base.breaks.x=c(0,1,2,3,4))

# Plot consensus time
plot.x.by.y(df.1,
            x="byz",
            y="final.time",
            xlab=expression("Number of Byzantine robots"),
            ylab=expression("Consensus time (s)"),
            out.name=sprintf("exp1_time.pdf"),
            report.dir=plot.dir,
            custom.base.breaks.x=c(0,1,2,3,4),
            custom.base.breaks.y=c(0,1000,2000))
